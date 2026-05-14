from telegram.ext import Application

from config.settings import get_settings

_application: Application | None = None


def get_application() -> Application:
    """Return the singleton Telegram Application."""
    global _application
    if _application is None:
        settings = get_settings()
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required to start the Telegram bot")
        _application = Application.builder().token(settings.telegram_bot_token).build()
    return _application
