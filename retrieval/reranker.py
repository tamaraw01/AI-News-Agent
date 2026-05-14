from functools import lru_cache
from typing import Any

from loguru import logger


@lru_cache(maxsize=1)
def _load_model() -> Any:
    """Lazy-load a cross encoder if an installed package provides one."""
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    except Exception as exc:
        logger.warning("Reranker unavailable, using retrieval order: %s", exc)
        return None


def rerank(query: str, articles: list[dict[str, Any]], top_k: int | None = None) -> list[dict[str, Any]]:
    """Rerank retrieval candidates with a cross encoder, falling back gracefully."""
    if not articles:
        return []

    model = _load_model()
    if model is None:
        return articles[:top_k] if top_k else articles

    try:
        pairs = [(query, f"{item.get('title', '')}\n{item.get('content', '')}") for item in articles]
        scores = model.predict(pairs)
        ranked = sorted(zip(articles, scores), key=lambda pair: float(pair[1]), reverse=True)
        output = []
        for item, score in ranked:
            enriched = dict(item)
            enriched["rerank_score"] = float(score)
            output.append(enriched)
        return output[:top_k] if top_k else output
    except Exception as exc:
        logger.warning("Reranker failed, using retrieval order: %s", exc)
        return articles[:top_k] if top_k else articles
