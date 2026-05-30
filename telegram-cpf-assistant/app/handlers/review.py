from __future__ import annotations

"""Handler da revisão semanal (/semana)."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.formatters import split_long_message
from app.security import authorized_only
from app.services import review_service as rs

log = logging.getLogger(__name__)


def register_review_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    @gate
    async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None:
            return
        text = rs.build_weekly_report(db_path)
        for chunk in split_long_message(text):
            await msg.reply_text(chunk)

    application.add_handler(CommandHandler("semana", semana))
    log.info("registered review handlers")