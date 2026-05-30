from __future__ import annotations

"""Handlers do domínio Casamento."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.formatters import format_money, parse_money
from app.repositories.wedding_repo import WeddingRepository
from app.security import authorized_only
from app.services import wedding_service as ws

log = logging.getLogger(__name__)


def register_wedding_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    def _repo() -> WeddingRepository:
        return WeddingRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        msg = update.effective_message
        if msg is not None:
            await msg.reply_text(text)

    @gate
    async def casamento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = " ".join(context.args).strip()
        if not text:
            await _reply(update, "Uso: /casamento <texto>.")
            return
        repo = _repo()
        try:
            item_id = ws.add_pendencia(repo, text)
        finally:
            repo.close()
        await _reply(update, f"Casamento #{item_id} (pendência): \"{text}\".")

    @gate
    async def casamento_pendencias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            rows = ws.list_pendencias(repo)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Sem pendências de casamento.")
            return
        body = "\n".join(f"#{r['id']:02d} {r['description']}" for r in rows)
        await _reply(update, f"Pendências de casamento ({len(rows)}):\n{body}")

    @gate
    async def casamento_pago(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await _reply(update, "Uso: /casamento_pago <descrição> [valor].")
            return
        args = list(context.args)
        amount = None
        if parse_money(args[-1]) is not None and len(args) > 1:
            amount = parse_money(args[-1])
            args = args[:-1]
        description = " ".join(args).strip()
        repo = _repo()
        try:
            item_id = ws.register_payment(repo, description, amount)
        finally:
            repo.close()
        val = f" {format_money(amount)}" if amount is not None else ""
        await _reply(update, f"Pagamento registrado #{item_id}: \"{description}\"{val}.")

    @gate
    async def casamento_fornecedor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) < 2:
            await _reply(update, "Uso: /casamento_fornecedor <nome> <status/obs>.")
            return
        vendor = context.args[0]
        note = " ".join(context.args[1:])
        repo = _repo()
        try:
            item_id = ws.register_vendor(repo, vendor, note)
        finally:
            repo.close()
        await _reply(update, f"Fornecedor #{item_id} ({vendor}): {note}.")

    for name, fn in [
        ("casamento", casamento),
        ("casamento_pendencias", casamento_pendencias),
        ("casamento_pago", casamento_pago),
        ("casamento_fornecedor", casamento_fornecedor),
    ]:
        application.add_handler(CommandHandler(name, fn))
    log.info("registered wedding handlers")
