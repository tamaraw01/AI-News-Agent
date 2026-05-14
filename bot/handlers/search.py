import asyncio
import re

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from agents.supervisor import handle_message
from notifications.scheduler_jobs import daily_digest_job
from notifications.dispatcher import split_and_send

HELP_TEXT = (
    "Saya siap.\n\n"
    "Tulis saja seperti bicara biasa. Saya bisa menangani permintaan berita dalam berbagai gaya bahasa.\n\n"
    "Contoh:\n"
    "• briefing hari ini\n"
    "• apa kabar ekonomi global?\n"
    "• brief me on AI regulation\n"
    "• summarize Japan markets\n\n"
    "Command cepat: /digest, /cari, /ping."
)

_DIGEST_PATTERNS = (
    "digest",
    "briefing",
    "ringkasan hari",
    "berita hari",
    "kabar hari",
    "pagi ini",
    "hari ini",
    "24 jam",
    "apa yang terjadi",
    "yang penting",
    "perkembangan penting",
    "daily brief",
    "news brief",
    "today's",
    "what happened",
    "what matters",
    "headlines",
    "résumé",
    "resume",
    "actualités",
    "noticias",
    "nachrichten",
    "ニュース",
)

_HELP_PATTERNS = (
    "bisa apa",
    "cara pakai",
    "bantuan",
    "help",
    "how to",
    "how do",
    "what can you do",
    "ayuda",
    "aide",
    "hilfe",
    "mulai",
)

_PING_PATTERNS = (
    "ping",
    "tes",
    "test",
    "online",
    "hidup",
    "alive",
    "ready",
    "up",
)

_GREETINGS = (
    "halo",
    "hai",
    "hello",
    "hi",
    "hey",
    "bonjour",
    "hola",
    "hallo",
    "ciao",
    "こんにちは",
    "pagi",
    "siang",
    "sore",
    "malam",
)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cari and /search commands."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        query = update.effective_message.text.replace("/cari", "").replace("/search", "").strip()
    if not query:
        await update.effective_message.reply_text("Ketik kata kunci setelah command, misalnya: /cari AI Indonesia")
        return

    await _run_search(update, context, query)


async def _handle_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle slash commands that arrive as plain text."""
    command_token, _, rest = text.partition(" ")
    command = command_token.split("@", 1)[0].lower()

    if command in {"/start", "/help"}:
        await update.effective_message.reply_text(HELP_TEXT)
        return True
    if command == "/ping":
        await update.effective_message.reply_text("pong")
        return True
    if command == "/digest":
        context.chat_data["digest_target_chat_id"] = update.effective_chat.id
        await daily_digest_job(context)
        context.chat_data.pop("digest_target_chat_id", None)
        return True
    if command in {"/cari", "/search"}:
        if not rest.strip():
            await update.effective_message.reply_text("Ketik kata kunci setelah command, misalnya: /cari AI Indonesia")
            return True
        await _run_search(update, context, rest.strip())
        return True

    await update.effective_message.reply_text("Command belum dikenali. Gunakan /help untuk melihat opsi.")
    return True


async def _run_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    result = await asyncio.to_thread(handle_message, query)
    await split_and_send(update.effective_chat.id, result["message"])


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_like_greeting(text: str) -> bool:
    normalized = _normalize(text)
    tokens = set(re.findall(r"\w+", normalized))
    return len(tokens) <= 4 and any(word in tokens for word in _GREETINGS)


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize(text)
    return any(pattern in normalized for pattern in patterns)


def _looks_like_digest_request(text: str) -> bool:
    normalized = _normalize(text)
    if _contains_any(normalized, _DIGEST_PATTERNS):
        return True
    direct_digest_words = {"digest", "briefing", "headlines"}
    direct_digest_phrases = {"today", "latest", "hari ini", "pagi ini", "24 jam"}
    tokens = set(re.findall(r"\w+", normalized))
    return normalized in direct_digest_phrases or (len(tokens) <= 3 and bool(tokens & direct_digest_words))


def _strip_search_prefix(text: str) -> str:
    normalized = text.strip()
    return re.sub(
        (
            r"^(tolong|coba|dong|please|pls|kindly|"
            r"carikan|cari|cek|lihat|pantau|kasih tahu|beritahu|rangkum|analisis|analisiskan|"
            r"search|find|check|look up|brief me on|summarize|analyse|analyze|"
            r"résume|resume|résumer|buscar|busca|rechercher|cherchez)\s+"
        ),
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip()


async def _send_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    context.chat_data["digest_target_chat_id"] = update.effective_chat.id
    await daily_digest_job(context)
    context.chat_data.pop("digest_target_chat_id", None)


async def text_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route natural chat into assistant actions."""
    query = update.effective_message.text.strip()
    if query.startswith("/") and await _handle_text_command(update, context, query):
        return

    normalized = _normalize(query)
    if _looks_like_greeting(query):
        await update.effective_message.reply_text("Siap. Kirim topik atau minta briefing hari ini.")
        return
    if _contains_any(normalized, _HELP_PATTERNS):
        await update.effective_message.reply_text(HELP_TEXT)
        return
    if _contains_any(normalized, _PING_PATTERNS) and len(normalized.split()) <= 5:
        await update.effective_message.reply_text("Saya online.")
        return
    if _looks_like_digest_request(normalized):
        await _send_digest(update, context)
        return

    await _run_search(update, context, _strip_search_prefix(query))
