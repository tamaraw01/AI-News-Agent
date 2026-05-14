import hashlib
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import create_engine, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from analysis.sentiment import get_sentiment_analyzer
from config import settings
from core.database import Base
from core.models import Article
from retrieval.vector_store import ChromaNewsStore


def _sync_database_url() -> str:
    """Return a sync SQLAlchemy URL for SQLite storage."""
    if settings.database_url.startswith("sqlite+aiosqlite:///"):
        return settings.database_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    return f"sqlite:///{settings.sqlite_path}"


def generate_url_hash(url: str) -> str:
    """Generate a deterministic hash for article deduplication."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def normalize_article(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw article payloads to the core Article schema."""
    url = str(raw.get("url", "")).strip()
    url_hash = generate_url_hash(url)
    title = str(raw.get("title", "")).strip()
    content = str(raw.get("content") or raw.get("summary") or "").strip()
    published_at = _parse_datetime(raw.get("published_at")) or datetime.utcnow()
    category = str(raw.get("category") or "general").strip().lower()

    return {
        "hash": url_hash,
        "url_hash": url_hash,
        "url": url,
        "title": title,
        "content": content,
        "summary": raw.get("summary"),
        "source": str(raw.get("source") or "unknown").strip(),
        "source_type": str(raw.get("source_type") or "unknown").strip(),
        "category": category,
        "language": str(raw.get("language") or "en"),
        "country": raw.get("country"),
        "url_image": raw.get("url_image") or raw.get("image_url"),
        "published_at": published_at,
    }


class SQLiteNewsStore:
    """SQLite store for news metadata and deduplication."""

    def __init__(self, sqlite_path: str | object = settings.sqlite_path) -> None:
        url = _sync_database_url() if sqlite_path == settings.sqlite_path else f"sqlite:///{sqlite_path}"
        self.engine = create_engine(url, future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def _article_payload(self, article_data: dict[str, Any]) -> dict[str, Any]:
        columns = Article.__table__.columns.keys()
        return {key: value for key, value in article_data.items() if key in columns}

    def add_article(self, article_data: dict[str, Any]) -> bool:
        """Insert a normalized article if it does not already exist."""
        payload = self._article_payload(article_data)
        payload["hash"] = payload.get("hash") or generate_url_hash(payload["url"])

        try:
            analyzer = get_sentiment_analyzer()
            scores = analyzer.polarity_scores(f"{payload.get('title', '')} {payload.get('content', '')}")
            compound = scores["compound"]
            payload["sentiment_score"] = compound
            payload["sentiment_label"] = "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"
        except Exception as exc:
            logger.debug("Sentiment enrichment skipped: %s", exc)

        with self.SessionLocal() as session:
            try:
                session.add(Article(**payload))
                session.commit()
                logger.info("Article saved: %s", payload["url"])
                return True
            except IntegrityError:
                session.rollback()
                logger.debug("Duplicate article skipped: %s", payload["url"])
                return False
            except Exception as exc:
                session.rollback()
                logger.exception("Failed to insert article: %s", exc)
                return False

    def get_by_url(self, url: str) -> dict[str, Any] | None:
        """Fetch a stored article by URL."""
        with self.SessionLocal() as session:
            row = session.execute(select(Article).where(Article.url == url)).scalar_one_or_none()
            return _article_to_dict(row) if row else None

    def query_recent(self, since: datetime) -> list[dict[str, Any]]:
        """Return recent articles since a given timestamp."""
        with self.SessionLocal() as session:
            rows = session.execute(select(Article).where(Article.created_at >= since)).scalars().all()
            return [_article_to_dict(row) for row in rows]

    def search_by_text(self, query: str, start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
        """Search stored metadata by keyword and date interval."""
        tokens = [token.strip().lower() for token in query.split() if len(token.strip()) >= 3]
        patterns = [f"%{token}%" for token in tokens] or [f"%{query.lower()}%"]
        text_filters = []
        for pattern in patterns:
            text_filters.extend(
                [
                    Article.title.ilike(pattern),
                    Article.content.ilike(pattern),
                    Article.summary.ilike(pattern),
                ]
            )
        with self.SessionLocal() as session:
            rows = (
                session.execute(
                    select(Article).where(
                        Article.published_at >= start_date,
                        Article.published_at <= end_date,
                        or_(*text_filters),
                    )
                )
                .scalars()
                .all()
            )
            return [_article_to_dict(row) for row in rows]


def _article_to_dict(article: Article) -> dict[str, Any]:
    data = {column.name: getattr(article, column.name) for column in Article.__table__.columns}
    data["url_hash"] = data.get("hash")
    return data


class NewsProcessor:
    """Processor orchestration for raw news ingestion."""

    def __init__(self, sqlite_path: str | object = settings.sqlite_path, chroma_dir: str | object = None) -> None:
        self.sqlite = SQLiteNewsStore(sqlite_path)
        self.chroma_dir = chroma_dir or settings.chroma_persist_dir

    def process_articles(self, raw_articles: list[dict[str, Any]]) -> int:
        """Normalize, deduplicate, store metadata and embeddings."""
        normalized = [normalize_article(item) for item in raw_articles if item.get("url")]
        stored = []
        for article in normalized:
            if self.sqlite.add_article(article):
                stored.append(article)

        if stored:
            try:
                ChromaNewsStore(self.chroma_dir).add_articles(stored)
            except Exception as exc:
                logger.warning("Embedding upsert skipped: %s", exc)

        logger.info("Processed %s new articles", len(stored))
        return len(stored)
