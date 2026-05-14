from collections import Counter
from datetime import datetime, timedelta
import re
from typing import Any

from loguru import logger
from sqlalchemy import and_, select
from telegram.ext import ContextTypes

from analysis.sentiment import get_sentiment_distribution
from analysis.trending import get_trending_topics
from bot.formatters import format_breaking_alert, format_daily_digest, format_search_results
from config import settings
from core.database import get_async_session
from core.models import Alert, Article, UserSession
from notifications.dispatcher import send_to_all, send_to_user


async def _active_users() -> list[str]:
    async with get_async_session() as session:
        result = await session.execute(select(UserSession.user_id))
        return [row[0] for row in result.all()]


def _article_to_digest_dict(article: Article) -> dict[str, Any]:
    return {
        "title": article.title,
        "source": article.source,
        "category": article.category,
        "country": article.country,
        "published_at": article.published_at,
        "summary": article.summary,
        "content": article.content,
        "url": article.url,
        "sentiment_label": article.sentiment_label,
        "sentiment_score": article.sentiment_score,
    }


def _select_diverse_articles(articles: list[Article], limit: int = 10) -> list[Article]:
    ranked = sorted(articles, key=_article_quality_score, reverse=True)
    selected: list[Article] = []
    seen_sources: set[str] = set()
    for article in ranked:
        if article.source in seen_sources and len(selected) < limit // 2:
            continue
        selected.append(article)
        seen_sources.add(article.source)
        if len(selected) >= limit:
            break
    for article in ranked:
        if article not in selected:
            selected.append(article)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _latin_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 1.0
    latin = sum(1 for char in letters if "A" <= char.upper() <= "Z")
    return latin / len(letters)


def _article_quality_score(article: Article) -> float:
    title = article.title or ""
    source = article.source or ""
    summary = article.summary or article.content or ""
    source_lower = source.lower()
    title_lower = title.lower().strip()

    weak_titles = {"similar topics", "related topics", "слични теми"}
    score = 0.0
    if title_lower in weak_titles or len(title) < 18:
        score -= 50
    if _latin_ratio(title) < 0.55:
        score -= 25
    if summary and len(summary) > 80:
        score += 14
    if article.url:
        score += 5
    if article.language in {"en", "id"}:
        score += 8
    if article.country in {"ID", "US", "GB", "IN", "JP", "AU", "CA"}:
        score += 3
    premium_sources = [
        "reuters",
        "bbc",
        "bloomberg",
        "financial times",
        "wsj",
        "cnbc",
        "dw",
        "france24",
        "al jazeera",
        "nature",
        "science",
        "mit technology review",
        "wired",
        "the verge",
        "techcrunch",
        "hackernews",
        "google news (id)",
    ]
    if any(name in source_lower for name in premium_sources):
        score += 18
    if article.sentiment_score is not None:
        score += min(abs(float(article.sentiment_score)) * 4, 4)
    if article.published_at:
        hours_old = max((datetime.utcnow() - article.published_at).total_seconds() / 3600, 0)
        score += max(0, 10 - hours_old / 3)
    return score


def _clean_briefing(text: str) -> str:
    text = text.replace("**", "")
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _article_context(articles: list[Article]) -> str:
    blocks = []
    for index, article in enumerate(articles, 1):
        summary = article.summary or article.content or ""
        blocks.append(
            "\n".join(
                [
                    f"{index}. {article.title}",
                    f"Sumber: {article.source}",
                    f"Kategori: {article.category}",
                    f"Negara: {article.country or 'unknown'}",
                    f"Waktu: {article.published_at}",
                    f"Sentimen: {article.sentiment_label} ({article.sentiment_score})",
                    f"Isi/Ringkasan: {summary[:900]}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _local_daily_briefing(articles: list[Article], sentiment_dist: dict[str, float], trending: list[dict]) -> str:
    sources = Counter(article.source for article in articles)
    categories = Counter(article.category for article in articles)
    countries = Counter(article.country for article in articles if article.country)
    top_titles = [article.title for article in articles[:5]]
    top_trends = ", ".join(str(item.get("category") or item.get("name")) for item in trending[:5]) or "belum ada sinyal kuat"

    return "\n".join(
        [
            "KESIMPULAN",
            f"Dalam 24 jam terakhir, sinyal berita paling kuat berasal dari {', '.join(name for name, _ in sources.most_common(3)) or 'sumber campuran'} dengan fokus {', '.join(name for name, _ in categories.most_common(3)) or 'general'}.",
            "",
            "POIN KUNCI",
            f"• Artikel: {len(articles)} dari {len(sources)} sumber.",
            f"• Sentimen: positif {sentiment_dist.get('positive', 0):.0%}, netral {sentiment_dist.get('neutral', 0):.0%}, negatif {sentiment_dist.get('negative', 0):.0%}.",
            f"• Fokus geografis: {', '.join(name for name, _ in countries.most_common(3)) or 'global/mixed'}.",
            f"• Topik trending: {top_trends}.",
            "",
            "SUMBER UTAMA",
            *(f"• {title}" for title in top_titles),
            "",
            "PERLU DIPANTAU",
            "• Isu yang mulai dilaporkan lintas sumber besar.",
            "• Lonjakan sentimen negatif pada ekonomi, konflik, kesehatan, atau teknologi.",
            "• Konfirmasi dari sumber primer.",
        ]
    )


def _llm_daily_briefing(articles: list[Article], sentiment_dist: dict[str, float], trending: list[dict]) -> str | None:
    if not settings.groq_api_key or not articles:
        return None
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        prompt = f"""
Anda adalah analis berita senior dan asisten eksekutif. Buat daily brief berbahasa Indonesia dari artikel yang diberikan.

Standar output:
- Jelas, pasti, to the point.
- Tanpa emoji.
- Tanpa Markdown bold/asterisk.
- Tanpa basa-basi.
- Jangan membuat daftar Who/Where/When mekanis.
- Jangan menulis N/A.
- Jangan mengarang fakta di luar artikel.
- Jika artikel campur aduk, rangkum pola besar dan sebutkan keterbatasan sinyal.
- Tulis seperti briefing asisten eksekutif: tajam, ringkas, operasional, bersih.
- Maksimal 260 kata.

Konteks metrik:
Jumlah artikel: {len(articles)}
Distribusi sentimen: {sentiment_dist}
Trending: {trending[:5]}

Struktur wajib:
KESIMPULAN
Satu paragraf pendek yang menjelaskan hal terpenting.

POIN KUNCI
3 bullet saja.

DAMPAK
Dampak praktis dalam 1 paragraf pendek.

PERLU DIPANTAU
2-3 hal konkret.

Artikel:
{_article_context(articles)}
"""
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=settings.temperature,
            max_tokens=max(settings.max_tokens_answer, 700),
            messages=[
                {
                    "role": "system",
                    "content": "Anda membuat briefing harian berita yang tajam, akurat, profesional, dan bebas hiasan berlebihan.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return _clean_briefing(response.choices[0].message.content or "")
    except Exception as exc:
        logger.warning("LLM daily briefing unavailable, using local fallback: %s", exc)
        return None


async def daily_digest_job(context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    """Build and send the daily digest."""
    target_chat_id = None
    if context is not None:
        target_chat_id = getattr(context, "chat_data", {}).get("digest_target_chat_id")

    since = datetime.utcnow() - timedelta(hours=24)
    async with get_async_session() as session:
        result = await session.execute(
            select(Article).where(Article.published_at >= since).order_by(Article.published_at.desc()).limit(80)
        )
        articles = result.scalars().all()

    trending = await get_trending_topics(hours=24, limit=10)
    selected_articles = _select_diverse_articles(articles, limit=10)
    sentiment_dist = get_sentiment_distribution(articles)
    briefing = (
        _llm_daily_briefing(selected_articles, sentiment_dist, trending)
        or _local_daily_briefing(selected_articles, sentiment_dist, trending)
        if articles
        else "Belum ada artikel baru dalam 24 jam terakhir."
    )
    digest = format_daily_digest(
        {
            "total_articles": len(articles),
            "sources": len({article.source for article in articles}),
            "trending_count": len(trending),
            "sentiment_dist": sentiment_dist,
            "briefing": briefing,
            "articles": [_article_to_digest_dict(article) for article in selected_articles[:6]],
            "trending_tags": ", ".join(str(item.get("category") or item.get("name")) for item in trending) or "N/A",
        }
    )
    for message in digest:
        if target_chat_id:
            await send_to_user(target_chat_id, message)
        else:
            await send_to_all(message, await _active_users())


async def alert_keyword_job(context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    """Send keyword alerts for active alerts."""
    since = datetime.utcnow() - timedelta(minutes=15)
    async with get_async_session() as session:
        alerts = (await session.execute(select(Alert).where(Alert.is_active.is_(True)))).scalars().all()
        for alert in alerts:
            pattern = f"%{alert.keyword}%"
            articles = (
                await session.execute(
                    select(Article).where(
                        and_(
                            Article.published_at >= since,
                            Article.title.ilike(pattern) | Article.content.ilike(pattern),
                        )
                    )
                )
            ).scalars().all()
            if not articles or not alert.user_id:
                continue
            await send_to_user(alert.user_id, format_search_results(articles, alert.keyword))
            alert.last_triggered_at = datetime.utcnow()
        await session.commit()


async def push_breaking_news(context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    """Push breaking-news articles marked by the ingestion scheduler."""
    async with get_async_session() as session:
        result = await session.execute(select(Article).where(Article.is_breaking.is_(True)).limit(10))
        articles = result.scalars().all()
        for article in articles:
            await send_to_all(format_breaking_alert(article))
            article.is_breaking = False
        await session.commit()
    if articles:
        logger.info("Pushed %s breaking articles", len(articles))


alert_check_job = alert_keyword_job
