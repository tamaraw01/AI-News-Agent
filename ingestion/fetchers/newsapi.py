"""NewsAPI fetcher for multi-country headlines."""

import json
from datetime import datetime

from config.settings import settings
from loguru import logger

from ingestion.fetchers.base import BaseFetcher, RawArticle


class NewsAPIFetcher(BaseFetcher):
    """Fetch headlines from NewsAPI with multi-country coverage."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"
    COUNTRIES = ["us", "gb", "id", "in", "au", "ca", "de", "fr", "jp", "br", "za", "ng", "mx"]

    @property
    def name(self) -> str:
        return "newsapi"

    @property
    def source_type(self) -> str:
        return "api"

    async def fetch(self) -> list[RawArticle]:
        """Fetch headlines from NewsAPI."""
        if not settings.newsapi_key:
            logger.warning("NewsAPI key not configured, skipping")
            return []

        articles = []

        for country in [item for item in self.COUNTRIES if item in settings.enabled_countries]:
            try:
                logger.debug(f"Fetching NewsAPI for country: {country}")
                page_size = min(settings.max_articles_per_source, 100)
                url = f"{self.BASE_URL}?country={country}&apiKey={settings.newsapi_key}&pageSize={page_size}"
                response_text = await self._get(url)
                data = json.loads(response_text)

                for article_data in data.get("articles", []):
                    article = RawArticle(
                        title=article_data.get("title", "").strip(),
                        url=article_data.get("url", "").strip(),
                        content=article_data.get("content"),
                        summary=article_data.get("description"),
                        source=article_data.get("source", {}).get("name", "NewsAPI"),
                        source_type="api",
                        published_at=self._parse_iso_date(article_data.get("publishedAt")),
                        language="en",
                        country=country.upper(),
                        image_url=article_data.get("urlToImage"),
                        raw_data={"author": article_data.get("author", "")},
                    )

                    if article.title and article.url:
                        articles.append(article)

            except Exception as e:
                logger.warning(f"NewsAPI fetch error for {country}: {e}")

        logger.info(f"NewsAPI fetcher: collected {len(articles)} articles")
        return articles

    def _parse_iso_date(self, date_str: str) -> datetime | None:
        """Parse ISO 8601 date string."""
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
