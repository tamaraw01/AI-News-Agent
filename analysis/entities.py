"""Entity extraction from article text."""

from typing import Optional

import spacy
from loguru import logger

from core.models import Article, EntityMention


# Singleton spaCy model
_nlp: Optional[spacy.Language] = None


def get_nlp_model() -> spacy.Language:
    """Get or load spaCy English model."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            raise
    return _nlp


async def extract_entities(article: Article) -> list[dict]:
    """Extract named entities from article.

    Args:
        article: Article to extract entities from

    Returns:
        List of dicts with entity_text, entity_type, frequency
    """
    if not article.content and not article.title:
        return []

    try:
        nlp = get_nlp_model()

        # Combine title + summary for entity extraction
        text = f"{article.title} {article.summary or ''}"

        if not text.strip():
            return []

        doc = nlp(text)

        # Count entity frequencies
        entity_counts = {}
        for ent in doc.ents:
            if len(ent.text.strip()) < 2:
                continue

            key = (ent.text.lower().strip(), ent.label_)
            entity_counts[key] = entity_counts.get(key, 0) + 1

        # Convert to list of dicts
        entities = []
        for (text_val, label), count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True):
            entities.append({"text": text_val, "type": label, "frequency": count})

        # Store in article
        article.entities = entities[:10]  # Keep top 10

        return entities

    except Exception as e:
        logger.error(f"Entity extraction error for article {article.id}: {e}")
        return []


def get_top_entities(articles: list[Article], limit: int = 10) -> list[dict]:
    """Get top entities across multiple articles.

    Args:
        articles: List of articles
        limit: Number of top entities to return

    Returns:
        List of top entities with their frequency
    """
    entity_freq = {}

    for article in articles:
        if not article.entities:
            continue

        for entity in article.entities:
            key = (entity.get("text"), entity.get("type"))
            entity_freq[key] = entity_freq.get(key, 0) + entity.get("frequency", 1)

    # Sort by frequency
    top_entities = []
    for (text, entity_type), freq in sorted(entity_freq.items(), key=lambda x: x[1], reverse=True)[:limit]:
        top_entities.append({"text": text, "type": entity_type, "total_frequency": freq})

    return top_entities
