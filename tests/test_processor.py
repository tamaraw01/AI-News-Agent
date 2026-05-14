import os
import tempfile
from datetime import datetime

from ingestion.processor import SQLiteNewsStore, generate_url_hash, normalize_article


def test_generate_url_hash_changes_for_different_urls() -> None:
    assert generate_url_hash("https://example.com/1") != generate_url_hash("https://example.com/2")


def test_normalize_article_sets_defaults() -> None:
    raw = {"url": "https://example.com", "title": "Judul", "content": "Konten", "source": "Sumber"}
    normalized = normalize_article(raw)
    assert normalized["url"] == raw["url"]
    assert normalized["title"] == "Judul"
    assert normalized["category"] == "general"
    assert normalized["url_hash"] == generate_url_hash(raw["url"])


def test_sqlite_news_store_add_and_dedupe() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "news.db")
        store = SQLiteNewsStore(sqlite_path=db_path)
        article = normalize_article(
            {
                "url": "https://example.com/article",
                "title": "Uji Artikel",
                "content": "Isi berita",
                "source": "Test",
                "category": "test",
                "published_at": datetime.utcnow().isoformat(),
                "source_type": "test",
            }
        )
        assert store.add_article(article) is True
        assert store.add_article(article) is False
