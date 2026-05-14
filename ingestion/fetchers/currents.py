"""Currents API fetcher for global news."""

import json
from datetime import datetime

from config.settings import settings
from loguru import logger

from ingestion.fetchers.base import BaseFetcher, RawArticle


class CurrentsFetcher(BaseFetcher):
    """Fetch news from Currents API."""

    BASE_URL = "https://api.currentsapi.services/v1/latest-news"

    @property
    def name(self) -> str:
        return "currents"

    @property
    def source_type(self) -> str:
        return "api"

    async def fetch(self) -> list[RawArticle]:
        """Fetch latest news from Currents API."""
        if not settings.currents_api_key:
            logger.warning("Currents API key not configured, skipping")
            return []

        articles = []

        try:
            params = {
                "apikey": settings.currents_api_key,
                "limit": 100,
                "lang": "en,id,de,fr,ja,ar,es,pt",
            }

            query_params = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{self.BASE_URL}?{query_params}"

            logger.debug("Fetching Currents API news")
            response_text = await self._get(url)
            data = json.loads(response_text)

            for article_data in data.get("news", []):
                article = RawArticle(
                    title=article_data.get("title", "").strip(),
                    url=article_data.get("url", "").strip(),
                    content=article_data.get("description"),
                    source=article_data.get("source", "Currents"),
                    source_type="api",
                    published_at=self._parse_iso_date(article_data.get("published")),
                    language=article_data.get("language", "en"),
                    country=None,
                    image_url=article_data.get("image"),
                    raw_data={"category": article_data.get("category", "")},
                )

                if article.title and article.url:
                    articles.append(article)

            logger.info(f"Currents fetcher: collected {len(articles)} articles")

        except Exception as e:
            logger.error(f"Currents API fetch error: {e}")

        return articles

    def _parse_iso_date(self, date_str: str) -> datetime | None:
        """Parse ISO 8601 date string."""
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
