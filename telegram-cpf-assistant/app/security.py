from __future__ import annotations

import logging
from functools import wraps
from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

HandlerFn = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def authorized_only(authorized_chat_id: int) -> Callable[[HandlerFn], HandlerFn]:
    def decorator(fn: HandlerFn) -> HandlerFn:
        @wraps(fn)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            chat = update.effective_chat
            incoming_id = chat.id if chat is not None else None
            if incoming_id != authorized_chat_id:
                log.warning(
                    "rejected message from unauthorized chat_id=%s (expected=%s)",
                    incoming_id,
                    authorized_chat_id,
                )
                return
            await fn(update, context)

        return wrapper

    return decorator
