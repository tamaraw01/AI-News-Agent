"""News fetcher registry for AI News Agent Pro."""

import asyncio
from dataclasses import asdict
from datetime import datetime
from typing import Any

from loguru import logger

from ingestion.fetchers.base import BaseFetcher, RawArticle
from ingestion.fetchers.currents import CurrentsFetcher
from ingestion.fetchers.gdelt import GDELTFetcher
from ingestion.fetchers.gnews import GNewsFetcher
from ingestion.fetchers.google_rss import GoogleNewsRSSFetcher
from ingestion.fetchers.hackernews import HackerNewsFetcher
from ingestion.fetchers.mediastack import MediaStackFetcher
from ingestion.fetchers.newsapi import NewsAPIFetcher
from ingestion.fetchers.reddit import RedditFetcher


FETCHER_CLASSES: tuple[type[BaseFetcher], ...] = (
    GoogleNewsRSSFetcher,
    NewsAPIFetcher,
    GDELTFetcher,
    HackerNewsFetcher,
    RedditFetcher,
    MediaStackFetcher,
    CurrentsFetcher,
    GNewsFetcher,
)


def get_fetchers() -> list[BaseFetcher]:
    """Create all configured fetchers."""
    return [fetcher_class() for fetcher_class in FETCHER_CLASSES]


def _raw_article_to_dict(article: RawArticle) -> dict[str, Any]:
    """Convert a RawArticle dataclass to processor input."""
    payload = asdict(article)
    published_at = payload.get("published_at")
    if isinstance(published_at, datetime):
        payload["published_at"] = published_at.isoformat()
    payload["category"] = article.raw_data.get("category") or "general"
    payload["url_image"] = payload.pop("image_url", None)
    return payload


async def fetch_all_sources() -> list[RawArticle]:
    """Fetch articles from all source adapters."""
    fetchers = get_fetchers()
    results = await asyncio.gather(
        *(fetcher.fetch() for fetcher in fetchers),
        return_exceptions=True,
    )

    articles: list[RawArticle] = []
    for fetcher, result in zip(fetchers, results):
        try:
            await fetcher.close()
        except Exception:
            logger.debug("Failed to close fetcher %s", fetcher.name)

        if isinstance(result, Exception):
            logger.warning("%s fetch failed: %s", fetcher.name, result)
            continue
        articles.extend(result)

    logger.info("Fetched %s articles from %s sources", len(articles), len(fetchers))
    return articles


async def fetch_all_article_batches() -> list[dict[str, Any]]:
    """Compatibility wrapper returning dict payloads for the processor."""
    return [_raw_article_to_dict(article) for article in await fetch_all_sources()]
