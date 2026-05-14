from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import func, select, update

from config import settings
from core.database import get_async_session
from core.models import Article


async def check_breaking() -> int:
    """Mark high-volume recent categories as breaking news."""
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    async with get_async_session() as session:
        result = await session.execute(
            select(Article.category, func.count(Article.id))
            .where(Article.published_at >= cutoff)
            .group_by(Article.category)
        )
        categories = [category for category, count in result.all() if count >= settings.breaking_news_velocity_threshold]
        if not categories:
            return 0

        await session.execute(
            update(Article)
            .where(Article.category.in_(categories), Article.published_at >= cutoff)
            .values(is_breaking=True)
        )
        await session.commit()
        logger.info("Marked breaking news categories: %s", categories)
        return len(categories)
