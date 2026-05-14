import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy import delete, select

from config import settings
from core.database import get_async_session
from core.models import Article
from ingestion.fetchers import fetch_all_article_batches
from ingestion.processor import NewsProcessor

_scheduler: AsyncIOScheduler | None = None


async def poll_news_job(sqlite_path: str | None = None, chroma_dir: str | None = None) -> None:
    """Fetch news from sources and process them into storage."""
    logger.info("Starting scheduled news poll")
    processor = NewsProcessor(sqlite_path=sqlite_path or settings.sqlite_path, chroma_dir=chroma_dir or settings.chroma_persist_dir)
    articles = await fetch_all_article_batches()
    count = processor.process_articles(articles)
    logger.info("Scheduled poll completed with %s new articles", count)


async def trending_detection_job() -> None:
    """Run lightweight trending detection without sending Telegram messages."""
    try:
        from analysis.trending import get_trending_topics

        topics = await get_trending_topics(hours=1, limit=10)
        logger.info("Trending detection completed with %s topics", len(topics))
    except Exception as exc:
        logger.warning("Trending detection skipped: %s", exc)


async def breaking_news_check_job() -> None:
    """Mark recent high-velocity categories as breaking in SQLite."""
    try:
        from notifications.breaking_news import check_breaking

        await check_breaking()
    except Exception as exc:
        logger.warning("Breaking news check skipped: %s", exc)


async def cleanup_old_articles_job() -> None:
    """Remove articles older than retention settings."""
    cutoff = datetime.utcnow() - timedelta(days=settings.article_retention_days)
    async with get_async_session() as session:
        await session.execute(delete(Article).where(Article.created_at < cutoff))
        await session.commit()
    logger.info("Old article cleanup completed")


def get_scheduler() -> AsyncIOScheduler:
    """Get the singleton APScheduler for ingestion/background detection."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
        _scheduler.add_job(
            poll_news_job,
            trigger=IntervalTrigger(minutes=settings.poll_interval_minutes),
            id="fetch_all_sources",
            next_run_time=datetime.utcnow(),
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        _scheduler.add_job(
            trending_detection_job,
            trigger=IntervalTrigger(minutes=5),
            id="trending_detection",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        _scheduler.add_job(
            breaking_news_check_job,
            trigger=IntervalTrigger(minutes=3),
            id="breaking_news_check",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        _scheduler.add_job(
            cleanup_old_articles_job,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_old_articles",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
    return _scheduler


def start_ingestion_scheduler(sqlite_path: str | None = None, chroma_dir: str | None = None) -> AsyncIOScheduler:
    """Start the ingestion scheduler."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
    logger.info("Ingestion scheduler started")
    return scheduler


async def _run_forever() -> None:
    start_ingestion_scheduler()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(_run_forever())
