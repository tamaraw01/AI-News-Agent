"""HTML formatters for Telegram messages."""

import html
import re
from typing import Any


def e(text: Any) -> str:
    """Escape HTML untuk Telegram."""
    return str(text if text is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


escape_html = e


def _get(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _clean_text(text: Any) -> str:
    value = html.unescape(str(text or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def format_article_card(article: Any) -> str:
    """Format article as HTML card for Telegram."""
    title = _get(article, "title", "Untitled")
    source = _get(article, "source", "Unknown")
    category = _get(article, "category", "general")
    language = _get(article, "language", "en")
    country = _get(article, "country", "Unknown")
    published_at = _get(article, "published_at", "N/A")
    if hasattr(published_at, "strftime"):
        published_at = published_at.strftime("%H:%M")
    summary = _clean_text(
        _get(article, "summary") or (_get(article, "content", "")[:200] if _get(article, "content") else "N/A")
    )
    sentiment_label = _get(article, "sentiment_label", "neutral") or "neutral"
    sentiment_score = _get(article, "sentiment_score", 0.0) or 0.0
    url = _get(article, "url") or _get(article, "id", "")
    emoji = {"positive": "🟢", "negative": "🔴", "neutral": "🔵"}.get(sentiment_label, "⚪")

    return f"""━━━━━━━━━━━━━━━━━━━━━
📰 <b>{e(title)}</b>

📍 <i>{e(source)} · {e(category)} · {e(published_at)}</i>
🗣️ {e(str(language).upper())} · 🏳️ {e(country)}

<b>Ringkasan:</b>
{e(summary)}

<b>Entitas Kunci:</b>
{_format_entities(article)}

<b>Sentimen:</b> {emoji} {e(str(sentiment_label).capitalize())} ({float(sentiment_score):.2f})

🔗 <a href="{e(url)}">Baca selengkapnya →</a>
━━━━━━━━━━━━━━━━━━━━━"""


def _format_entities(article: Any) -> str:
    entities = _get(article, "entities", None)
    if not entities:
        return "—"
    entity_types = {"PERSON": "👤", "ORG": "🏢", "GPE": "🌍", "EVENT": "📅", "PRODUCT": "📦"}
    parts = []
    for entity in entities[:5]:
        entity_type = str(entity.get("type", "")).upper()
        parts.append(f"{entity_types.get(entity_type, '•')} {e(entity.get('text', 'Unknown'))}")
    return " · ".join(parts) if parts else "—"


def format_search_results(articles: list[Any], query: str) -> str:
    """Format search results."""
    articles = [article for article in articles if (_get(article, "id") or "") != "none"]
    if not articles:
        return f"""🔍 <b>HASIL PENCARIAN: "{e(query)}"</b>

Belum ada artikel yang cocok.

Coba kata kunci yang lebih spesifik, misalnya:
• AI Indonesia
• ekonomi global
• teknologi terbaru
• konflik Timur Tengah"""

    results = [
        f"""🔍 <b>HASIL PENCARIAN: "{e(query)}"</b>

📊 Ditemukan {len(articles)} artikel"""
    ]
    for i, article in enumerate(articles[:10], 1):
        title = _get(article, "title", "Untitled")
        source = _get(article, "source", "Unknown")
        url = _get(article, "url") or _get(article, "id", "")
        results.append(
            f"""

{i}. <b>{e(str(title)[:80])}</b>
   📍 {e(source)}
   🔗 <a href="{e(url)}">Baca →</a>"""
        )
    return "\n".join(results)


def _compact_time(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %H:%M")
    text = str(value or "")
    return text[:16].replace("T", " ") if text else "N/A"


def _article_digest_line(article: Any, index: int) -> str:
    title = str(_get(article, "title", "Untitled")).strip()
    source = _get(article, "source", "Unknown")
    category = _get(article, "category", "general")
    published_at = _compact_time(_get(article, "published_at", ""))
    summary = _clean_text(_get(article, "summary") or _get(article, "content") or "")
    if len(summary) > 360:
        summary = summary[:357].rstrip() + "..."
    url = _get(article, "url") or _get(article, "id", "")
    sentiment_label = _get(article, "sentiment_label", "") or "neutral"
    sentiment_score = _get(article, "sentiment_score", 0.0) or 0.0

    summary_block = f"\n   <b>Ringkasan:</b> {e(summary)}" if summary else ""
    return f"""
{index}. <b>{e(title)}</b>
   {e(source)} · {e(category)} · {e(published_at)}
   Sentimen: {e(str(sentiment_label).capitalize())} ({float(sentiment_score):.2f}){summary_block}
   <a href="{e(url)}">Buka sumber</a>"""


def format_intelligence_brief(query: str, articles: list[Any], analysis: str | None) -> str:
    """Format a search result as an analytical Telegram briefing."""
    articles = [article for article in articles if (_get(article, "id") or "") != "none"]
    if not articles:
        return f"""<b>INTELLIGENCE BRIEF: "{e(query)}"</b>

Belum ada artikel yang cukup relevan di database lokal.

Saran query:
• Gunakan nama negara, organisasi, atau peristiwa spesifik.
• Contoh: ekonomi Indonesia rupiah, AI chip Nvidia, konflik Gaza."""

    source_count = len({str(_get(article, "source") or "") for article in articles if _get(article, "source")})
    categories = sorted({str(_get(article, "category") or "general") for article in articles})
    analysis_block = e(analysis or "Analisis belum tersedia.")

    header = f"""<b>INTELLIGENCE BRIEF: "{e(query)}"</b>

<b>CAKUPAN</b>
• Artikel dianalisis: {len(articles)}
• Sumber aktif: {source_count}
• Kategori: {e(", ".join(categories[:5]))}

<b>RANGKUMAN DAN ANALISIS</b>
{analysis_block}

<b>ARTIKEL PENDUKUNG</b>"""

    article_blocks = [_article_digest_line(article, index) for index, article in enumerate(articles[:5], 1)]
    footer = "\n\n<b>Catatan:</b> Analisis dibuat dari artikel yang sudah tersimpan lokal. Link tetap disediakan untuk verifikasi."
    return "\n".join([header, *article_blocks, footer])


def format_trending(topics: list[dict]) -> str:
    """Format trending topics."""
    trends = ["🔥 <b>TRENDING SAAT INI</b>\n\nTop topik paling viral hari ini:"]
    for i, topic in enumerate(topics[:10], 1):
        name = topic.get("name") or topic.get("category") or "Unknown"
        trends.append(f"{i}. #{e(name)} ({e(topic.get('article_count', 0))} artikel)")
    return "\n".join(trends)


def format_breaking_alert(article: Any) -> str:
    """Format breaking news alert."""
    title = _get(article, "title", "Breaking news")
    source = _get(article, "source", "Unknown")
    summary = _get(article, "summary") or _get(article, "content", "")
    url = _get(article, "url") or _get(article, "id", "")
    return f"""🚨 <b>BREAKING NEWS</b>

<b>{e(title)}</b>
📍 {e(source)}

{e(str(summary)[:700])}

🔗 <a href="{e(url)}">Baca selengkapnya</a>"""


def format_daily_digest(data: dict) -> list[str]:
    """Format daily digest into HTML message chunks."""
    sentiment = data.get("sentiment_dist", {}) or {}
    sentiment_line = (
        f"positif {float(sentiment.get('positive', 0)):.0%}, "
        f"netral {float(sentiment.get('neutral', 0)):.0%}, "
        f"negatif {float(sentiment.get('negative', 0)):.0%}"
    )
    briefing = e(data.get("briefing", "Belum ada briefing."))
    articles = data.get("articles", []) or []
    article_blocks = [
        _article_digest_line(article, index) for index, article in enumerate(articles[:6], 1)
    ]

    digest = f"""<b>WORLD NEWS DIGEST</b>
Edisi Pagi

<b>STATUS</b>
• Artikel dianalisis: {e(data.get('total_articles', 0))}
• Sumber aktif: {e(data.get('sources', 0))}
• Topik trending: {e(data.get('trending_count', 0))}
• Sentimen: {e(sentiment_line)}

<b>BRIEFING</b>
{briefing}

<b>SUMBER KUNCI</b>
{''.join(article_blocks)}

<b>CATATAN</b>
Briefing dibuat dari artikel yang sudah tersimpan lokal. Link disediakan hanya untuk verifikasi."""
    return split_message(digest)


def split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split message if it exceeds Telegram's max length."""
    if len(text) <= max_len:
        return [text]

    messages = []
    current = ""
    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 <= max_len:
            current += paragraph + "\n"
        else:
            if current:
                messages.append(current)
            current = paragraph[:max_len - 1] + "\n" if len(paragraph) >= max_len else paragraph + "\n"
    if current:
        messages.append(current)
    return messages
