"""MediaStack fetcher for multi-country news API."""

import json
from datetime import datetime

from config.settings import settings
from loguru import logger

from ingestion.fetchers.base import BaseFetcher, RawArticle


class MediaStackFetcher(BaseFetcher):
    """Fetch news from MediaStack API with multi-country coverage."""

    BASE_URL = "http://api.mediastack.com/v1/news"
    COUNTRIES = ["us", "gb", "id", "in", "au", "ca", "de", "fr", "jp", "br", "za", "ng", "mx", "eg", "pk", "bd"]
    LANGUAGES = ["en", "id", "de", "fr", "ja", "pt", "ar", "es"]

    @property
    def name(self) -> str:
        return "mediastack"

    @property
    def source_type(self) -> str:
        return "api"

    async def fetch(self) -> list[RawArticle]:
        """Fetch news from MediaStack."""
        if not settings.mediastack_api_key:
            logger.warning("MediaStack key not configured, skipping")
            return []

        articles = []

        # MediaStack has limited free tier (500 req/month), so fetch just once
        try:
            params = {
                "access_key": settings.mediastack_api_key,
                "limit": 100,
                "languages": ",".join(self.LANGUAGES[:3]),  # Limit languages to conserve quota
            }

            query_params = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{self.BASE_URL}?{query_params}"

            logger.debug("Fetching MediaStack news")
            response_text = await self._get(url)
            data = json.loads(response_text)

            for article_data in data.get("data", []):
                article = RawArticle(
                    title=article_data.get("title", "").strip(),
                    url=article_data.get("url", "").strip(),
                    content=article_data.get("description"),
                    source=article_data.get("source", "MediaStack"),
                    source_type="api",
                    published_at=self._parse_iso_date(article_data.get("published_at")),
                    language=article_data.get("language", "en"),
                    country=article_data.get("country"),
                    image_url=article_data.get("image"),
                    raw_data={"category": article_data.get("category", "")},
                )

                if article.title and article.url:
                    articles.append(article)

            logger.info(f"MediaStack fetcher: collected {len(articles)} articles")

        except Exception as e:
            logger.error(f"MediaStack fetch error: {e}")

        return articles

    def _parse_iso_date(self, date_str: str) -> datetime | None:
        """Parse ISO 8601 date string."""
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
