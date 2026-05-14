import hashlib
from datetime import datetime, timedelta
from itertools import groupby
from typing import Any

from loguru import logger

from retrieval.search import SearchService
from retrieval.vector_store import ChromaNewsStore
from config import settings
from ingestion.processor import SQLiteNewsStore
from .llm import generate_text


def _ensure_services() -> tuple[SQLiteNewsStore, ChromaNewsStore, SearchService]:
    """Initialize SQLite and Chroma services for agent tools."""
    sqlite_store = SQLiteNewsStore(settings.sqlite_path)
    chroma_store = ChromaNewsStore(settings.chroma_persist_dir)
    search_service = SearchService(chroma_store=chroma_store)
    return sqlite_store, chroma_store, search_service


def search_news(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search news articles semantically in ChromaDB."""
    _, _, search_service = _ensure_services()
    logger.info("search_news query=%s top_k=%s", query, top_k)
    results = search_service.semantic_search(query=query, top_k=top_k)
    return [dict(article) for article in results]


def get_trending(category: str = "all", hours: int = 24) -> list[dict[str, Any]]:
    """Return top trending topics or articles based on recent metadata counts."""
    sqlite_store, _, _ = _ensure_services()
    since = datetime.utcnow() - timedelta(hours=hours)
    articles = sqlite_store.query_recent(since)
    if category != "all":
        articles = [item for item in articles if item.get("category") == category]

    items = sorted(articles, key=lambda item: item.get("published_at", ""), reverse=True)
    top = []
    for key, group in groupby(items, key=lambda item: item.get("source")):
        group_list = list(group)
        top.append({
            "source": key,
            "count": len(group_list),
            "latest_title": group_list[0].get("title", ""),
        })
    return top[:5]


def analyze_sentiment(text: str) -> dict[str, Any]:
    """Perform a lightweight sentiment analysis on text content."""
    text_lower = text.lower()
    positive = sum(word in text_lower for word in ["baik", "positif", "menguntungkan", "naik", "menang", "terobosan"])
    negative = sum(word in text_lower for word in ["buruk", "negatif", "kerugian", "jatuh", "gagal", "kekhawatiran"])
    if positive > negative:
        label = "positif"
        score = min(0.9, 0.5 + (positive - negative) * 0.1)
    elif negative > positive:
        label = "negatif"
        score = min(0.9, 0.5 + (negative - positive) * 0.1)
    else:
        label = "netral"
        score = 0.5
    logger.info("analyze_sentiment label=%s score=%s", label, score)
    return {"label": label, "score": score}


def summarize_article(url: str) -> str:
    """Create a short article summary based on stored news content."""
    sqlite_store = SQLiteNewsStore(settings.sqlite_path)
    article = sqlite_store.get_by_url(url)
    if not article:
        message = "Artikel tidak ditemukan untuk ringkasan."
        logger.warning(message)
        return message

    content = article.get("content") or article.get("title", "")
    if len(content) > 320:
        prompt = (
            "Ringkas artikel berikut dalam 3-5 kalimat dengan bahasa Indonesia:\n\n" + content
        )
        summary = generate_text(prompt, max_tokens=180)
    else:
        summary = content
    logger.info("summarize_article url=%s summary_len=%s", url, len(summary))
    return summary


def find_related(topic: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Find articles related to a topic using semantic similarity."""
    _, _, search_service = _ensure_services()
    results = search_service.semantic_search(query=topic, top_k=top_k)
    return [dict(article) for article in results]


def get_timeline(topic: str, days: int = 7) -> list[dict[str, Any]]:
    """Generate a timeline of activity for a topic over a range of days."""
    sqlite_store = SQLiteNewsStore(settings.sqlite_path)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    articles = sqlite_store.search_by_text(topic, start_date, end_date)
    timeline: dict[str, int] = {}
    for article in articles:
        date_key = article["published_at"][:10]
        timeline[date_key] = timeline.get(date_key, 0) + 1
    return [{"date": date, "count": count} for date, count in sorted(timeline.items())]
