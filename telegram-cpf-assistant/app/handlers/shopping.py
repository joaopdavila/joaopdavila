from __future__ import annotations

"""Handlers do domínio Compras."""

import logging
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.repositories.shopping_repo import ShoppingRepository
from app.security import authorized_only
from app.services import shopping_service as ss

log = logging.getLogger(__name__)

_CONFIRM_WINDOW = 60  # segundos para confirmar /limpar_compras


def register_shopping_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    def _repo() -> ShoppingRepository:
        return ShoppingRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        msg = update.effective_message
        if msg is not None:
            await msg.reply_text(text)

    @gate
    async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        item = " ".join(context.args).strip()
        if not item:
            await _reply(update, "Uso: /comprar <item>.")
            return
        repo = _repo()
        try:
            outcome, data, count = ss.add(repo, item)
        finally:
            repo.close()
        if outcome == "duplicate":
            await _reply(update, f"\"{item}\" já está na lista (#{data['id']:02d}). Nada a fazer.")
        else:
            await _reply(update, f"Adicionado #{data:02d}: {item}. Pendentes: {count}.")

    @gate
    async def compras(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            rows = ss.list_pending(repo)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Lista de compras vazia.")
            return
        body = "\n".join(f"#{r['id']:02d} {r['item']}" for r in rows)
        await _reply(update, f"Compras pendentes ({len(rows)}):\n{body}")

    @gate
    async def comprado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        arg = " ".join(context.args).strip()
        if not arg:
            await _reply(update, "Uso: /comprado <id ou item>.")
            return
        repo = _repo()
        try:
            outcome, data = ss.mark_bought(repo, arg)
        finally:
            repo.close()
        if outcome == "bought":
            await _reply(update, f"Comprado: {data['item']}.")
        elif outcome == "ambiguous":
            lst = "\n".join(f"#{r['id']:02d} {r['item']}" for r in data)
            await _reply(update, f"{len(data)} itens encontrados:\n{lst}\nUse /comprado <id>.")
        else:
            await _reply(update, "Item não encontrado na lista pendente.")

    @gate
    async def limpar_compras(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            n = ss.count_bought(repo)
            if n == 0:
                await _reply(update, "Nada para limpar (nenhum item comprado).")
                return
            last = context.chat_data.get("confirm_clear_shopping", 0)
            now = time.monotonic()
            if now - last <= _CONFIRM_WINDOW:
                context.chat_data.pop("confirm_clear_shopping", None)
                removed = ss.clear_bought(repo)
                await _reply(update, f"{removed} item(ns) comprado(s) removido(s) da lista.")
            else:
                context.chat_data["confirm_clear_shopping"] = now
                await _reply(
                    update,
                    f"Isso remove {n} item(ns) comprado(s). Confirme repetindo "
                    f"/limpar_compras em até {_CONFIRM_WINDOW}s.",
                )
        finally:
            repo.close()

    for name, fn in [
        ("comprar", comprar),
        ("compras", compras),
        ("comprado", comprado),
        ("limpar_compras", limpar_compras),
    ]:
        application.add_handler(CommandHandler(name, fn))
    log.info("registered shopping handlers")
