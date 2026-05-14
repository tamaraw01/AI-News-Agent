"""HackerNews fetcher for tech news and discussions."""

import json
from datetime import datetime

from loguru import logger

from config import settings
from ingestion.fetchers.base import BaseFetcher, RawArticle


class HackerNewsFetcher(BaseFetcher):
    """Fetch trending tech news and discussions from HackerNews."""

    BASE_URL = "https://hn.algolia.com/api/v1"

    @property
    def name(self) -> str:
        return "hackernews"

    @property
    def source_type(self) -> str:
        return "api"

    async def fetch(self) -> list[RawArticle]:
        """Fetch top stories from HackerNews API."""
        articles = []

        try:
            # Fetch front page stories
            url = f"{self.BASE_URL}/search?tags=front_page&hitsPerPage={settings.max_articles_per_source}"
            response_text = await self._get(url)
            data = json.loads(response_text)

            for item in data.get("hits", []):
                if item.get("points", 0) < 50:  # Filter low engagement
                    continue

                article = RawArticle(
                    title=item.get("title", "").strip(),
                    url=item.get("url", "") or f"https://news.ycombinator.com/item?id={item.get('objectID')}",
                    source="HackerNews",
                    source_type="api",
                    published_at=self._parse_unix_timestamp(item.get("created_at_i")),
                    language="en",
                    country="US",
                    raw_data={
                        "points": item.get("points", 0),
                        "num_comments": item.get("num_comments", 0),
                        "author": item.get("author", ""),
                    },
                )

                if article.title and article.url:
                    articles.append(article)

            logger.info(f"HackerNews fetcher: collected {len(articles)} articles")
        except Exception as e:
            logger.error(f"HackerNews fetch error: {e}")

        return articles

    def _parse_unix_timestamp(self, timestamp: int) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        if not timestamp:
            return None
        try:
            return datetime.fromtimestamp(timestamp)
        except Exception:
            return None
