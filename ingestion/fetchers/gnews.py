"""GNews fetcher for global news (optional/fallback)."""

import json
from datetime import datetime

from config.settings import settings
from loguru import logger

from ingestion.fetchers.base import BaseFetcher, RawArticle


class GNewsFetcher(BaseFetcher):
    """Fetch news from GNews.io API."""

    BASE_URL = "https://gnews.io/api/v4/top-headlines"

    @property
    def name(self) -> str:
        return "gnews"

    @property
    def source_type(self) -> str:
        return "api"

    async def fetch(self) -> list[RawArticle]:
        """Fetch top headlines from GNews."""
        if not settings.gnews_api_key:
            logger.warning("GNews API key not configured, skipping")
            return []

        articles = []

        try:
            params = {
                "lang": "en",
                "country": "US",
                "max": min(settings.max_articles_per_source, 100),
                "apikey": settings.gnews_api_key,
            }

            query_params = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{self.BASE_URL}?{query_params}"

            logger.debug("Fetching GNews headlines")
            response_text = await self._get(url)
            data = json.loads(response_text)

            for article_data in data.get("articles", []):
                article = RawArticle(
                    title=article_data.get("title", "").strip(),
                    url=article_data.get("url", "").strip(),
                    content=article_data.get("content"),
                    summary=article_data.get("description"),
                    source=article_data.get("source", {}).get("name", "GNews"),
                    source_type="api",
                    published_at=self._parse_iso_date(article_data.get("publishedAt")),
                    language="en",
                    country="US",
                    image_url=article_data.get("image"),
                    raw_data={},
                )

                if article.title and article.url:
                    articles.append(article)

            logger.info(f"GNews fetcher: collected {len(articles)} articles")

        except Exception as e:
            logger.warning(f"GNews fetch error: {e}")

        return articles

    def _parse_iso_date(self, date_str: str) -> datetime | None:
        """Parse ISO 8601 date string."""
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
