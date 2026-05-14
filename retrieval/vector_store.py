import os
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.config import Settings
from loguru import logger

from config import settings

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
try:
    from chromadb.telemetry.product.posthog import Posthog

    Posthog.capture = lambda self, *args, **kwargs: None
except Exception:
    logger.debug("Chroma telemetry patch skipped")


def _simple_embedding(text: str, dimensions: int = 384) -> list[float]:
    """Create a deterministic lightweight embedding when ML packages are absent."""
    vector = [0.0] * dimensions
    for index, byte in enumerate(text.encode("utf-8", errors="ignore")):
        vector[(byte + index) % dimensions] += 1.0
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


class ChromaNewsStore:
    """Local persistent ChromaDB wrapper for news embeddings."""

    def __init__(self, chroma_dir: str | object) -> None:
        try:
            self.client = chromadb.PersistentClient(
                path=str(chroma_dir),
                settings=Settings(anonymized_telemetry=False),
            )
        except Exception:
            logger.debug("Falling back to legacy Chroma settings")
            self.client = chromadb.PersistentClient(
                path=str(chroma_dir),
                settings=Settings(chroma_db_impl="duckdb+parquet"),
            )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"source": "ai_news_agent"},
        )

    def add_articles(self, articles: list[dict[str, Any]]) -> None:
        """Store a list of normalized articles into ChromaDB."""
        document_ids = [article["url"] for article in articles]
        metadatas = [
            {
                "title": article["title"],
                "source": article["source"],
                "published_at": article["published_at"],
                "category": article["category"],
                "summary": article.get("summary") or "",
            }
            for article in articles
        ]
        documents = [article["content"] or article["title"] for article in articles]
        try:
            self.collection.upsert(
                ids=document_ids,
                metadatas=metadatas,
                documents=documents,
                embeddings=[_simple_embedding(document) for document in documents],
            )
            logger.info("Upserted %s documents into ChromaDB", len(articles))
        except Exception as exc:
            logger.exception("Failed to upsert articles into ChromaDB: %s", exc)

    def semantic_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Query ChromaDB for semantically similar news content."""
        try:
            results = self.collection.query(query_embeddings=[_simple_embedding(query)], n_results=top_k)
            hits = []
            for idx in range(len(results["ids"][0])):
                hits.append(
                    {
                        "id": results["ids"][0][idx],
                        "score": results["distances"][0][idx],
                        "metadata": results["metadatas"][0][idx],
                    }
                )
            return hits
        except Exception as exc:
            logger.exception("Chroma semantic search failed: %s", exc)
            return []

    def get_article(self, url: str) -> dict[str, Any] | None:
        """Retrieve article metadata from Chroma by URL."""
        try:
            results = self.collection.get(ids=[url])
            if results["ids"]:
                return {
                    "id": results["ids"][0],
                    "metadata": results["metadatas"][0],
                    "document": results["documents"][0],
                }
        except Exception:
            logger.exception("Failed to retrieve article from Chroma for %s", url)
        return None


@lru_cache(maxsize=1)
def get_store() -> ChromaNewsStore:
    """Get the singleton Chroma store."""
    return ChromaNewsStore(settings.chroma_persist_dir)


def get_client() -> Any:
    """Get the singleton Chroma client."""
    return get_store().client
