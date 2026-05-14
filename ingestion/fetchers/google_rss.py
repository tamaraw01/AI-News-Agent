"""Google News RSS fetcher with global coverage."""

from datetime import datetime

import feedparser
from loguru import logger

from config import settings
from ingestion.fetchers.base import BaseFetcher, RawArticle


# Global Google News RSS URLs
GOOGLE_NEWS_TOPICS = {
    "world": "https://news.google.com/rss/headlines/section/topic/WORLD",
    "nation": "https://news.google.com/rss/headlines/section/topic/NATION",
    "business": "https://news.google.com/rss/headlines/section/topic/BUSINESS",
    "technology": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY",
    "entertainment": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT",
    "sports": "https://news.google.com/rss/headlines/section/topic/SPORTS",
    "science": "https://news.google.com/rss/headlines/section/topic/SCIENCE",
    "health": "https://news.google.com/rss/headlines/section/topic/HEALTH",
}

# Country editions with their parameters
GOOGLE_NEWS_COUNTRIES = {
    "us": "?hl=en-US&gl=US&ceid=US:en",
    "gb": "?hl=en-GB&gl=GB&ceid=GB:en",
    "id": "?hl=id&gl=ID&ceid=ID:id",
    "in": "?hl=en-IN&gl=IN&ceid=IN:en",
    "au": "?hl=en-AU&gl=AU&ceid=AU:en",
    "ca": "?hl=en-CA&gl=CA&ceid=CA:en",
    "de": "?hl=de&gl=DE&ceid=DE:de",
    "fr": "?hl=fr&gl=FR&ceid=FR:fr",
    "jp": "?hl=ja&gl=JP&ceid=JP:ja",
    "br": "?hl=pt-BR&gl=BR&ceid=BR:pt-419",
    "za": "?hl=en&gl=ZA&ceid=ZA:en",
    "ng": "?hl=en&gl=NG&ceid=NG:en",
    "mx": "?hl=es-419&gl=MX&ceid=MX:es-419",
    "eg": "?hl=ar&gl=EG&ceid=EG:ar",
}

# International media RSS feeds
INTERNATIONAL_RSS_FEEDS = {
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "BBC Science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "Reuters Top News": "https://feeds.reuters.com/reuters/topNews",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "DW English": "https://rss.dw.com/rdf/rss-en-all",
    "France24": "https://www.france24.com/en/rss",
    "RFI": "https://www.rfi.fr/en/rss",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Wired": "https://www.wired.com/feed/rss",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "Nature": "https://www.nature.com/nature.rss",
    "Science Magazine": "https://www.science.org/rss/news_current.xml",
    "Financial Times": "https://www.ft.com/rss/home",
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Forbes": "https://www.forbes.com/real-time/feed2/",
    "WSJ": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
}


class GoogleNewsRSSFetcher(BaseFetcher):
    """Fetch news from Google News RSS with global coverage."""

    @property
    def name(self) -> str:
        return "google_news_rss"

    @property
    def source_type(self) -> str:
        return "rss"

    async def fetch(self) -> list[RawArticle]:
        """Fetch articles from Google News RSS topics and countries."""
        articles = []

        # Fetch from topic feeds
        for topic, url in GOOGLE_NEWS_TOPICS.items():
            logger.debug(f"Fetching Google News topic: {topic}")
            try:
                feed_articles = await self._fetch_feed(url, source_name=f"Google News ({topic})")
                articles.extend(feed_articles)
            except Exception as e:
                logger.warning(f"Failed to fetch Google News topic {topic}: {e}")

        # Fetch from country editions
        for country, params in GOOGLE_NEWS_COUNTRIES.items():
            if country not in settings.enabled_countries:
                continue
            url = f"https://news.google.com/rss{params}"
            logger.debug(f"Fetching Google News country: {country}")
            try:
                feed_articles = await self._fetch_feed(url, source_name=f"Google News ({country})", country=country)
                articles.extend(feed_articles)
            except Exception as e:
                logger.warning(f"Failed to fetch Google News country {country}: {e}")

        # Fetch from international media feeds
        for media_name, url in INTERNATIONAL_RSS_FEEDS.items():
            logger.debug(f"Fetching international feed: {media_name}")
            try:
                feed_articles = await self._fetch_feed(url, source_name=media_name)
                articles.extend(feed_articles)
            except Exception as e:
                logger.warning(f"Failed to fetch {media_name}: {e}")

        logger.info(f"Google News RSS fetcher: collected {len(articles)} articles")
        return articles

    async def _fetch_feed(self, url: str, source_name: str, country: str = None) -> list[RawArticle]:
        """Fetch and parse a single RSS feed.

        Args:
            url: RSS feed URL
            source_name: Display name for the source
            country: Country code if applicable

        Returns:
            List of raw articles
        """
        try:
            html = await self._get(url)
            feed = feedparser.parse(html)

            articles = []
            for entry in feed.entries[: settings.max_articles_per_source]:
                article = RawArticle(
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", "").strip(),
                    content=entry.get("summary", "").strip() or None,
                    source=source_name,
                    source_type="rss",
                    published_at=self._parse_date(entry.get("published", None)),
                    language="en",  # Default to English for Google News
                    country=country,
                    image_url=self._extract_image(entry),
                    raw_data={"feed_url": url, "feed_title": feed.feed.get("title", "")},
                )

                if article.title and article.url:
                    articles.append(article)

            return articles
        except Exception as e:
            logger.error(f"Error parsing feed {url}: {e}")
            return []

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse RSS date string to datetime."""
        if not date_str:
            return None

        try:
            # Try RFC 2822 format (most common in RSS)
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(date_str)
        except Exception:
            try:
                # Try ISO format
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                return None

    def _extract_image(self, entry: dict) -> str | None:
        """Extract image URL from RSS entry."""
        if "media_content" in entry:
            return entry.media_content[0].get("url")
        if "image" in entry:
            return entry.image.get("url")
        return None
