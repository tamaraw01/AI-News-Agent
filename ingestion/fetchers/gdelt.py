"""GDELT (Global Event Database) fetcher for global news events."""

import json
from datetime import datetime

from loguru import logger

from config import settings
from ingestion.fetchers.base import BaseFetcher, RawArticle


class GDELTFetcher(BaseFetcher):
    """Fetch global news events from GDELT Event Database."""

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    # Rotating query topics for balanced coverage
    QUERIES = [
        "global economy crisis",
        "technology AI breakthrough",
        "geopolitics conflict",
        "climate environment",
        "health pandemic disease",
        "election democracy",
        "science discovery",
        "Indonesia Southeast Asia",
        "India Asia news",
        "Africa news development",
    ]

    @property
    def name(self) -> str:
        return "gdelt"

    @property
    def source_type(self) -> str:
        return "api"

    def __init__(self, *args, query_index: int = 0, **kwargs):
        """Initialize GDELT fetcher.

        Args:
            query_index: Index of query to rotate through QUERIES list
        """
        super().__init__(*args, **kwargs)
        self.query_index = query_index

    async def fetch(self) -> list[RawArticle]:
        """Fetch articles from GDELT Event Database."""
        articles = []

        try:
            # Use rotating query for variety
            query = self.QUERIES[self.query_index % len(self.QUERIES)]
            logger.debug(f"GDELT fetching with query: {query}")

            url = (
                f"{self.BASE_URL}?mode=artlist&maxrecords={settings.max_articles_per_source}"
                f"&format=json&query={query}"
            )
            response_text = await self._get(url)
            data = json.loads(response_text)

            for article_data in data.get("articles", []):
                article = RawArticle(
                    title=article_data.get("title", "").strip(),
                    url=article_data.get("url", "").strip(),
                    source=article_data.get("sourcecountry", "Unknown"),
                    source_type="api",
                    published_at=self._parse_date(article_data.get("seendate")),
                    language=article_data.get("language", "en"),
                    country=article_data.get("sourcecountry"),
                    image_url=article_data.get("socialimage", None),
                    raw_data={
                        "tone": article_data.get("tone", 0),
                        "eventcode": article_data.get("eventcodes", []),
                    },
                )

                if article.title and article.url:
                    articles.append(article)

            logger.info(f"GDELT fetcher: collected {len(articles)} articles")
        except Exception as e:
            logger.error(f"GDELT fetch error: {e}")

        return articles

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse GDELT date format (YYYYMMDDHHMMSS)."""
        if not date_str or len(date_str) < 8:
            return None

        try:
            # GDELT date format: YYYYMMDD or YYYYMMDDHHMMSS
            if len(date_str) >= 14:
                return datetime.strptime(date_str[:14], "%Y%m%d%H%M%S")
            else:
                return datetime.strptime(date_str[:8], "%Y%m%d")
        except Exception:
            return None
