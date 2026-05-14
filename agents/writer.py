from collections import Counter
from datetime import datetime
import re
from typing import Any

from loguru import logger

from bot.formatters import format_intelligence_brief
from config import settings


def _get(item: dict[str, Any], key: str, default: Any = "") -> Any:
    return item.get(key, default)


def _article_context(articles: list[dict[str, Any]]) -> str:
    blocks = []
    for index, article in enumerate(articles[:8], 1):
        title = _get(article, "title")
        source = _get(article, "source")
        published_at = _get(article, "published_at")
        category = _get(article, "category")
        summary = _get(article, "summary") or _get(article, "content")
        blocks.append(
            "\n".join(
                [
                    f"{index}. {title}",
                    f"Sumber: {source}",
                    f"Waktu: {published_at}",
                    f"Kategori: {category}",
                    f"Isi/Ringkasan: {str(summary)[:900]}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _response_language(query: str) -> str:
    """Best-effort language choice for the assistant response."""
    lowered = query.strip().lower()
    indonesian_markers = {
        "apa",
        "berita",
        "kabar",
        "ringkas",
        "rangkum",
        "analisis",
        "hari",
        "ini",
        "tentang",
        "ekonomi",
        "dunia",
    }
    if any(marker in lowered.split() for marker in indonesian_markers):
        return "Indonesian"

    try:
        from langdetect import detect

        code = detect(query)
    except Exception:
        code = "id"

    languages = {
        "id": "Indonesian",
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "pt": "Portuguese",
        "it": "Italian",
        "nl": "Dutch",
        "ja": "Japanese",
        "ko": "Korean",
        "zh-cn": "Chinese",
        "zh-tw": "Chinese",
        "ar": "Arabic",
        "hi": "Hindi",
    }
    return languages.get(code, "Indonesian")


def _local_analysis(query: str, articles: list[dict[str, Any]]) -> str:
    sources = Counter(str(_get(article, "source") or "Unknown") for article in articles)
    categories = Counter(str(_get(article, "category") or "general") for article in articles)
    top_sources = ", ".join(name for name, _ in sources.most_common(3)) or "belum jelas"
    top_categories = ", ".join(name for name, _ in categories.most_common(3)) or "general"
    titles = [str(_get(article, "title")) for article in articles[:3]]

    return "\n".join(
        [
            "KESIMPULAN",
            f"{query} muncul dalam {len(articles)} artikel relevan. Sinyal terkuat datang dari {top_sources}; kategori dominan: {top_categories}.",
            "",
            "POIN KUNCI",
            *(f"• {title}" for title in titles if title),
            "",
            "DAMPAK",
            "Pantau apakah isu ini mulai muncul lintas sumber kredibel. Jika artikel pendukung masih campur, query perlu dibuat lebih spesifik agar analisis lebih presisi.",
            "",
            "PERLU DIPANTAU",
            "• Perkembangan baru dalam beberapa jam ke depan.",
            "• Konfirmasi dari sumber primer atau media besar.",
            "• Dampak langsung ke ekonomi, kebijakan, publik, atau sektor terkait.",
        ]
    )


def _clean_analysis(text: str) -> str:
    """Normalize LLM output for Telegram HTML mode."""
    text = text.replace("**", "")
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _llm_analysis(query: str, articles: list[dict[str, Any]]) -> str | None:
    if not settings.groq_api_key or not articles:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        response_language = _response_language(query)
        prompt = f"""
You are a senior news analyst and executive assistant. Write a concise Telegram briefing in {response_language}.

User query: {query}
Analysis time: {datetime.utcnow().isoformat()} UTC

Rules:
- Be direct, clean, professional, and specific.
- No greetings, no filler, no motivational language, no emoji.
- Do not invent facts beyond the articles.
- If evidence is weak, say it plainly.
- Avoid mechanical Who/What/Where/When lists.
- Use plain text only. No Markdown.
- Maximum 220 words.

Required structure:
KESIMPULAN
One clear bottom line.

POIN KUNCI
3 bullets only.

DAMPAK
1 short paragraph.

PERLU DIPANTAU
2-3 concrete items.

Articles:
{_article_context(articles)}
"""
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=settings.temperature,
            max_tokens=settings.max_tokens_answer,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write sharp executive news briefings. "
                        "Use the user's language when possible. Be brief, accurate, and plain."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        return _clean_analysis(content) or None
    except Exception as exc:
        logger.warning("LLM briefing unavailable, using local analysis: %s", exc)
        return None


def format_results(query: str, articles: list[dict[str, Any]]) -> str:
    """Format agent search results as a high-signal Telegram briefing."""
    if not articles:
        return format_intelligence_brief(query, [], None)

    analysis = _llm_analysis(query, articles) or _clean_analysis(_local_analysis(query, articles))
    return format_intelligence_brief(query, articles, analysis)
