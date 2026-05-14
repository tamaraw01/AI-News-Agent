"""Trending topic detection and analysis."""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from core.database import get_async_session
from core.models import Article, Topic


async def get_trending_topics(
    hours: int = 24, limit: int = 10, velocity_threshold: float = 2.0
) -> list[dict]:
    """Get trending topics based on article velocity.

    Args:
        hours: Time window in hours
        limit: Number of topics to return
        velocity_threshold: Minimum trend velocity to qualify as trending

    Returns:
        List of trending topics with metadata
    """
    try:
        async with get_async_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Get article counts per category in last N hours
            recent_articles = (
                select(Article.category, func.count(Article.id).label("count"))
                .where(Article.published_at >= cutoff_time)
                .group_by(Article.category)
                .order_by(func.count(Article.id).desc())
                .limit(limit)
            )

            results = await session.execute(recent_articles)
            trends = results.all()

            return [{"category": cat, "article_count": count} for cat, count in trends]

    except Exception as e:
        logger.error(f"Error getting trending topics: {e}")
        return []


async def detect_breaking(topic: str, threshold: int = 10, window_minutes: int = 30) -> bool:
    """Detect if topic is breaking news.

    Args:
        topic: Topic/category to check
        threshold: Minimum articles in window to qualify as breaking
        window_minutes: Time window in minutes

    Returns:
        True if breaking news detected
    """
    try:
        async with get_async_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)

            count_query = (
                select(func.count(Article.id)).where(
                    and_(
                        Article.category == topic,
                        Article.published_at >= cutoff_time,
                    )
                )
            )

            result = await session.execute(count_query)
            count = result.scalar() or 0

            is_breaking = count >= threshold
            if is_breaking:
                logger.info(f"Breaking news detected: {topic} ({count} articles)")

            return is_breaking

    except Exception as e:
        logger.error(f"Error detecting breaking news: {e}")
        return False


async def get_topic_timeline(
    topic: str, days: int = 7
) -> list[dict]:
    """Get article volume timeline for a topic.

    Args:
        topic: Topic/category
        days: Number of days to analyze

    Returns:
        List of daily volume data
    """
    try:
        async with get_async_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Query articles grouped by day
            query = (
                select(
                    func.date(Article.published_at).label("day"),
                    func.count(Article.id).label("count"),
                )
                .where(
                    and_(
                        Article.category == topic,
                        Article.published_at >= cutoff_date,
                    )
                )
                .group_by(func.date(Article.published_at))
                .order_by(func.date(Article.published_at))
            )

            results = await session.execute(query)
            timeline = results.all()

            return [{"date": str(day), "articles": count} for day, count in timeline]

    except Exception as e:
        logger.error(f"Error getting topic timeline: {e}")
        return []
