"""Article clustering using embeddings."""

import json
from typing import Optional

from loguru import logger
from sklearn.cluster import HDBSCAN

from core.models import Article, Topic


async def cluster_articles(articles: list[Article], embeddings: list[list[float]]) -> dict:
    """Cluster articles using their embeddings.

    Args:
        articles: List of articles
        embeddings: List of embedding vectors

    Returns:
        Dict mapping cluster_id to articles and cluster label
    """
    if len(articles) < 3:
        return {0: {"articles": articles, "label": "Miscellaneous"}}

    try:
        # Cluster using HDBSCAN
        clusterer = HDBSCAN(min_cluster_size=3, min_samples=1)
        labels = clusterer.fit_predict(embeddings)

        # Group articles by cluster
        clusters = {}
        for idx, (article, label) in enumerate(zip(articles, labels)):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(article)

        # Generate label for each cluster (using top 3 titles)
        result = {}
        for cluster_id, cluster_articles in clusters.items():
            # Simple label generation: use first article title as base
            top_titles = [a.title for a in cluster_articles[:3]]
            label = self._generate_cluster_label(top_titles)

            result[cluster_id] = {
                "articles": cluster_articles,
                "label": label,
                "size": len(cluster_articles),
            }

        logger.info(f"Clustered {len(articles)} articles into {len(result)} clusters")
        return result

    except Exception as e:
        logger.error(f"Clustering error: {e}")
        return {0: {"articles": articles, "label": "Error"}}


def _generate_cluster_label(titles: list[str], max_words: int = 4) -> str:
    """Generate cluster label from titles.

    Args:
        titles: List of article titles
        max_words: Maximum words in label

    Returns:
        Cluster label string
    """
    if not titles:
        return "Cluster"

    # Extract common words from titles (simple approach)
    words = set()
    for title in titles:
        title_words = set(title.lower().split()[:5])
        words.update(title_words)

    # Filter common words and make label
    common_words = [w for w in list(words)[:max_words] if len(w) > 3]
    label = " ".join(common_words).title()

    return label if label else titles[0][:50]
