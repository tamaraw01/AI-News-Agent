from typing import Any

from retrieval.reranker import rerank
from retrieval.search import hybrid_search


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Find and rerank articles for a user query."""
    candidates = hybrid_search(query=query, top_k=max(top_k, 10))
    return rerank(query=query, articles=candidates, top_k=top_k)
