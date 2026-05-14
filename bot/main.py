import asyncio
import signal
import threading
from datetime import time

from loguru import logger
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.app import get_application
from bot.handlers.search import search_command, text_search
from config import settings
from core.database import init_db
from ingestion.scheduler import get_scheduler
from notifications.scheduler_jobs import alert_check_job, daily_digest_job, push_breaking_news

_ingestion_loop: asyncio.AbstractEventLoop | None = None
_ingestion_thread: threading.Thread | None = None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register the Telegram user for future digests."""
    from sqlalchemy import select

    from core.database import get_async_session
    from core.models import UserSession

    user = update.effective_user
    if user:
        async with get_async_session() as session:
            existing = (
                await session.execute(select(UserSession).where(UserSession.user_id == str(user.id)))
            ).scalar_one_or_none()
            if existing is None:
                session.add(UserSession(user_id=str(user.id), username=user.username))
            elif user.username:
                existing.username = user.username
            await session.commit()

    await update.effective_message.reply_text(
        "Saya siap.\n\n"
        "Kamu bisa bicara natural saja. Contoh:\n"
        "• kasih briefing hari ini\n"
        "• apa kabar ekonomi global?\n"
        "• rangkum berita AI Indonesia\n\n"
        "Command tetap tersedia kalau dibutuhkan: /digest, /cari, /ping."
    )


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the daily digest to the current chat on demand."""
    context.chat_data["digest_target_chat_id"] = update.effective_chat.id
    await daily_digest_job(context)
    context.chat_data.pop("digest_target_chat_id", None)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return a small health response from the Telegram bot."""
    await update.effective_message.reply_text("pong")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Telegram handler errors and notify the current chat when possible."""
    logger.exception("Telegram handler failed: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Maaf, terjadi error saat memproses pesan.")


async def shutdown(app, scheduler) -> None:
    """Gracefully stop bot and scheduler."""
    logger.info("Shutting down...")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
    if _ingestion_loop and _ingestion_loop.is_running():
        _ingestion_loop.call_soon_threadsafe(_ingestion_loop.stop)
    await app.stop()
    await app.shutdown()


def handle_signal(sig, app, scheduler) -> None:
    """Schedule graceful shutdown on process signals."""
    asyncio.get_event_loop().create_task(shutdown(app, scheduler))


def _register_handlers(app) -> None:
    app.add_handler(CommandHandler(["start", "help"], start_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("digest", digest_command))
    app.add_handler(CommandHandler(["cari", "search"], search_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_search))
    app.add_error_handler(error_handler)


def _register_jobs(app) -> None:
    if app.job_queue is None:
        logger.warning("PTB JobQueue unavailable; install python-telegram-bot[job-queue]")
        return
    app.job_queue.run_daily(
        daily_digest_job,
        time=time(hour=settings.daily_digest_hour, minute=settings.daily_digest_minute),
        name="daily_digest_job",
    )
    app.job_queue.run_repeating(alert_check_job, interval=900, first=60, name="alert_keyword_job")
    app.job_queue.run_repeating(push_breaking_news, interval=180, first=30, name="push_breaking_news")


def _run_ingestion_scheduler() -> None:
    """Run ingestion jobs on their own event loop so Telegram polling stays responsive."""
    global _ingestion_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _ingestion_loop = loop

    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
    logger.info("Ingestion scheduler started in background thread")

    try:
        loop.run_forever()
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        loop.close()


def _start_ingestion_thread() -> None:
    global _ingestion_thread
    if _ingestion_thread and _ingestion_thread.is_alive():
        return
    _ingestion_thread = threading.Thread(
        target=_run_ingestion_scheduler,
        name="ingestion-scheduler",
        daemon=True,
    )
    _ingestion_thread.start()


def main() -> None:
    """Start Telegram bot polling and ingestion scheduler."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())

    app = get_application()
    _register_handlers(app)
    _register_jobs(app)

    signal.signal(signal.SIGTERM, lambda s, f: handle_signal(s, app, None))
    signal.signal(signal.SIGINT, lambda s, f: handle_signal(s, app, None))

    _start_ingestion_thread()
    logger.info("Starting Telegram bot polling")
    app.run_polling()


if __name__ == "__main__":
    main()
