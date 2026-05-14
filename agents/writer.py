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


def _local_analysis(query: str, articles: list[dict[str, Any]]) -> str:
    sources = Counter(str(_get(article, "source") or "Unknown") for article in articles)
    categories = Counter(str(_get(article, "category") or "general") for article in articles)
    top_sources = ", ".join(name for name, _ in sources.most_common(3)) or "belum jelas"
    top_categories = ", ".join(name for name, _ in categories.most_common(3)) or "general"
    titles = [str(_get(article, "title")) for article in articles[:3]]

    return "\n".join(
        [
            "INTI CEPAT",
            f"Topik {query} muncul dari {len(articles)} artikel paling relevan yang sudah tersimpan.",
            f"Sumber dominan: {top_sources}. Kategori dominan: {top_categories}.",
            "",
            "SINYAL UTAMA",
            *(f"• {title}" for title in titles if title),
            "",
            "MAKNA PRAKTIS",
            "Gunakan daftar artikel pendukung di bawah sebagai bukti utama. Jika judul-judulnya belum benar-benar satu tema, query perlu dibuat lebih spesifik agar analisis makin tajam.",
            "",
            "YANG PERLU DIPANTAU",
            "• Apakah sumber lain mulai melaporkan pola yang sama.",
            "• Apakah ada perkembangan terbaru dalam beberapa jam ke depan.",
            "• Apakah dampaknya lokal, regional, atau global.",
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
        prompt = f"""
Anda adalah analis berita senior. Buat briefing Telegram berbahasa Indonesia berdasarkan artikel yang diberikan.

Query pengguna: {query}
Tanggal analisis: {datetime.utcnow().isoformat()} UTC

Aturan:
- Jangan mengarang fakta di luar artikel.
- Jika bukti artikel kurang kuat, katakan dengan jelas.
- Fokus agar pembaca tidak perlu membuka web kecuali ingin verifikasi detail.
- Jangan gunakan Markdown. Gunakan teks polos dengan heading singkat.
- Maksimal 450 kata.

Struktur wajib:
INTI 30 DETIK:
3-5 bullet paling penting.

ANALISIS:
Apa pola besar, kenapa penting, dan dampaknya.

RISIKO / KETIDAKPASTIAN:
Apa yang belum jelas atau bisa berubah.

YANG PERLU DIPANTAU:
3 hal konkret untuk dipantau berikutnya.

Artikel:
{_article_context(articles)}
"""
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=settings.temperature,
            max_tokens=settings.max_tokens_answer,
            messages=[
                {
                    "role": "system",
                    "content": "Anda menulis briefing berita yang padat, tajam, akurat, dan mudah dibaca di Telegram.",
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
