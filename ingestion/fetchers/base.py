"""Base classes and utilities for news fetchers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class RawArticle:
    """Raw article from fetcher before processing."""

    title: str
    url: str
    content: Optional[str] = None
    summary: Optional[str] = None
    source: str = ""
    source_type: str = ""  # rss, api, reddit, etc
    published_at: Optional[datetime] = None
    language: str = "en"
    country: Optional[str] = None
    image_url: Optional[str] = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize fields."""
        self.title = self.title.strip() if self.title else ""
        self.url = self.url.strip() if self.url else ""
        if self.content:
            self.content = self.content.strip()
        if self.summary:
            self.summary = self.summary.strip()


class BaseFetcher(ABC):
    """Abstract base class for news fetchers."""

    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """Initialize fetcher.

        Args:
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[httpx.AsyncClient] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Fetcher name (e.g., 'google_rss', 'newsapi')."""
        return ""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Source type (e.g., 'rss', 'api', 'reddit')."""
        return ""

    @abstractmethod
    async def fetch(self) -> list[RawArticle]:
        """Fetch articles from source.

        Returns:
            List of raw articles
        """
        return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _request(
        self,
        url: str,
        method: str = "GET",
        **kwargs,
    ) -> str:
        """Make HTTP request with retry logic.

        Args:
            url: Request URL
            method: HTTP method
            **kwargs: Additional arguments for httpx

        Returns:
            Response text

        Raises:
            httpx.HTTPError: If request fails after retries
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=self.timeout)

        try:
            response = await self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.warning(f"{self.name}: Request failed - {e}")
            raise

    async def _get(self, url: str, **kwargs) -> str:
        """GET request."""
        return await self._request(url, method="GET", **kwargs)

    async def _post(self, url: str, **kwargs) -> str:
        """POST request."""
        return await self._request(url, method="POST", **kwargs)

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.aclose()

    async def __aenter__(self):
        """Async context manager enter."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
