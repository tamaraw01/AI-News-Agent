"""Sentiment analysis for articles."""

from typing import Optional

from loguru import logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from core.models import Article


# Initialize VADER sentiment analyzer
_sentiment_analyzer: Optional[SentimentIntensityAnalyzer] = None


def get_sentiment_analyzer() -> SentimentIntensityAnalyzer:
    """Get or create singleton VADER sentiment analyzer."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentIntensityAnalyzer()
    return _sentiment_analyzer


async def batch_sentiment(articles: list[Article]) -> list[Article]:
    """Analyze sentiment for batch of articles using VADER.

    Args:
        articles: List of articles to analyze

    Returns:
        Same articles with sentiment_score and sentiment_label updated
    """
    analyzer = get_sentiment_analyzer()

    for article in articles:
        try:
            # Combine title and summary for better sentiment analysis
            text = f"{article.title} {article.summary or ''}"

            if not text.strip():
                article.sentiment_score = 0.0
                article.sentiment_label = "neutral"
                continue

            # Get VADER sentiment scores
            scores = analyzer.polarity_scores(text)
            compound = scores["compound"]  # -1.0 to 1.0

            article.sentiment_score = compound
            # Classify: -1 to -0.05: negative, -0.05 to 0.05: neutral, 0.05 to 1: positive
            if compound >= 0.05:
                article.sentiment_label = "positive"
            elif compound <= -0.05:
                article.sentiment_label = "negative"
            else:
                article.sentiment_label = "neutral"

        except Exception as e:
            logger.warning(f"Sentiment analysis error for article {article.id}: {e}")
            article.sentiment_score = 0.0
            article.sentiment_label = "neutral"

    return articles


def get_sentiment_distribution(articles: list[Article]) -> dict[str, float]:
    """Calculate sentiment distribution for articles.

    Args:
        articles: List of articles

    Returns:
        Dict with percentages: {"positive": 0.3, "neutral": 0.5, "negative": 0.2}
    """
    if not articles:
        return {"positive": 0.0, "neutral": 1.0, "negative": 0.0}

    counts = {"positive": 0, "neutral": 0, "negative": 0}

    for article in articles:
        label = article.sentiment_label or "neutral"
        if label in counts:
            counts[label] += 1

    total = len(articles)
    return {
        "positive": round(counts["positive"] / total, 3),
        "neutral": round(counts["neutral"] / total, 3),
        "negative": round(counts["negative"] / total, 3),
    }
