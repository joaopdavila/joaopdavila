from __future__ import annotations

"""Helpers genéricos para jobs do scheduler."""

import logging
import time

from app.config import Settings

log = logging.getLogger(__name__)

_WINDOW = 2 * 3600  # janela de captura de resposta livre (2h)


async def send(application, settings: Settings, text: str) -> None:
    try:
        await application.bot.send_message(
            chat_id=settings.telegram_chat_id, text=text
        )
    except Exception:  # noqa: BLE001
        log.exception("failed to send scheduled message")


def set_pending(application, settings: Settings, kind: str) -> None:
    """Marca o chat autorizado como aguardando resposta de check-in/fechamento."""
    pending = application.bot_data.setdefault("pending_response", {})
    pending[settings.telegram_chat_id] = (kind, time.monotonic() + _WINDOW)
