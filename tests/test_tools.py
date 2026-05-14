from agent.tools import analyze_sentiment, get_timeline, summarize_article
from ingestion.processor import normalize_article


def test_analyze_sentiment_positive() -> None:
    result = analyze_sentiment("Perusahaan mengalami keuntungan besar dan pertumbuhan positif.")
    assert result["label"] == "positif"
    assert result["score"] > 0.5


def test_analyze_sentiment_negative() -> None:
    result = analyze_sentiment("Krisis ekonomi menyebabkan kerugian besar dan kekhawatiran.")
    assert result["label"] == "negatif"
    assert result["score"] > 0.5


def test_summarize_article_missing_url() -> None:
    summary = summarize_article("https://example.com/nonexistent")
    assert "tidak ditemukan" in summary.lower()


def test_get_timeline_empty() -> None:
    timeline = get_timeline("nonexistent-topic", days=1)
    assert isinstance(timeline, list)
    assert timeline == []
