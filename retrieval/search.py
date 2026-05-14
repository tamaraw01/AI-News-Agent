from datetime import datetime, timedelta
import re
from typing import Any

from loguru import logger

from config import settings
from ingestion.processor import SQLiteNewsStore
from .vector_store import ChromaNewsStore


class SearchService:
    """Search service for semantic retrieval and keyword hybrid queries."""

    def __init__(self, chroma_store: ChromaNewsStore) -> None:
        self.chroma_store = chroma_store

    def semantic_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-k relevant articles to a query."""
        hits = self.chroma_store.semantic_search(query=query, top_k=top_k)
        articles = []
        for item in hits:
            metadata = item.get("metadata", {})
            articles.append(
                {
                    "id": item.get("id"),
                    "url": item.get("id"),
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "published_at": metadata.get("published_at", ""),
                    "category": metadata.get("category", ""),
                    "summary": metadata.get("summary", ""),
                    "content": item.get("document", ""),
                    "score": item.get("score"),
                }
            )
        logger.info("SearchService returned %s results for query %s", len(articles), query)
        return articles

    def hybrid_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Combine semantic and simple keyword search heuristics."""
        return hybrid_search(query=query, top_k=top_k, chroma_store=self.chroma_store)


def _rrf_merge(result_sets: list[list[dict[str, Any]]], top_k: int) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for results in result_sets:
        for rank, item in enumerate(results, 1):
            item_id = str(item.get("id") or item.get("url") or item.get("title"))
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (60 + rank)
            by_id[item_id] = item

    merged = sorted(by_id.values(), key=lambda item: scores[str(item.get("id") or item.get("url") or item.get("title"))], reverse=True)
    for item in merged:
        item["score"] = scores[str(item.get("id") or item.get("url") or item.get("title"))]
    return merged[:top_k]


def _keyword_search(query: str, top_k: int) -> list[dict[str, Any]]:
    store = SQLiteNewsStore(settings.sqlite_path)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=settings.article_retention_days)
    results = store.search_by_text(query, start_date, end_date)
    query_lower = query.lower().strip()
    tokens = [token.lower() for token in re.findall(r"[\w]+", query) if len(token) >= 2]

    def relevance(item: dict[str, Any]) -> tuple[int, str]:
        title = str(item.get("title") or "").lower()
        content = str(item.get("content") or "").lower()
        summary = str(item.get("summary") or "").lower()
        body = f"{summary} {content}"
        score = 0
        if query_lower and query_lower in title:
            score += 30
        if query_lower and query_lower in body:
            score += 10
        for token in tokens:
            pattern = rf"\b{re.escape(token)}\b"
            if re.search(pattern, title):
                score += 8
            elif token in title:
                score += 4
            if re.search(pattern, body):
                score += 2
            elif token in body:
                score += 1
        published_at = item.get("published_at") or ""
        return score, str(published_at)

    ranked = sorted(results, key=relevance, reverse=True)
    return [
        {
            "id": item.get("url"),
            "url": item.get("url"),
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "published_at": item.get("published_at", ""),
            "category": item.get("category", ""),
            "summary": item.get("summary", ""),
            "content": item.get("content", ""),
            "language": item.get("language", ""),
            "country": item.get("country", ""),
            "sentiment_label": item.get("sentiment_label", ""),
            "sentiment_score": item.get("sentiment_score", 0.0),
            "score": 0.0,
        }
        for item in ranked[:top_k]
    ]


def hybrid_search(query: str, top_k: int = 5, chroma_store: ChromaNewsStore | None = None) -> list[dict[str, Any]]:
    """Run semantic + keyword retrieval and merge with reciprocal-rank fusion."""
    keyword_results = _keyword_search(query, top_k=top_k)
    if keyword_results:
        return keyword_results[:top_k]

    semantic_results: list[dict[str, Any]] = []
    try:
        store = chroma_store or ChromaNewsStore(settings.chroma_persist_dir)
        semantic_results = SearchService(store).semantic_search(query=query, top_k=top_k)
    except Exception as exc:
        logger.warning("Semantic search skipped: %s", exc)

    merged = _rrf_merge([semantic_results], top_k=top_k)
    if merged:
        return merged
    return []
