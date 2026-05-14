import asyncio
from typing import Any

from loguru import logger
from telegram.constants import ParseMode

from bot.app import get_application
from bot.formatters import split_message
from config import settings


async def split_and_send(chat_id: str | int, text: str, **kwargs: Any) -> None:
    """Send a Telegram message, splitting chunks over Telegram's limit."""
    application = get_application()
    kwargs.setdefault("parse_mode", ParseMode.HTML)
    chunks = split_message(text)
    for chunk in chunks:
        await application.bot.send_message(chat_id=chat_id, text=chunk, **kwargs)
        await asyncio.sleep(0.3)


async def send_to_user(user_id: str | int, text: str, **kwargs: Any) -> None:
    """Send a message to a single user."""
    try:
        await split_and_send(user_id, text, **kwargs)
    except Exception as exc:
        logger.exception("Failed to send Telegram message to %s: %s", user_id, exc)


async def send_to_all(text: str, user_ids: list[str | int] | None = None, **kwargs: Any) -> None:
    """Send a message to configured broadcast recipients."""
    recipients = [
        *([value for value in user_ids or [] if value]),
        *[
            value
            for value in [
                settings.telegram_channel_id,
                settings.telegram_chat_id,
                settings.telegram_admin_id,
            ]
            if value
        ],
    ]
    for recipient in dict.fromkeys(str(item) for item in recipients if item):
        await send_to_user(recipient, text, **kwargs)
