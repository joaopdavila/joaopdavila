from __future__ import annotations

"""Handlers do domínio Notas."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.repositories.notes_repo import NotesRepository
from app.security import authorized_only
from app.services import notes_service as ns

log = logging.getLogger(__name__)


def _line(row) -> str:
    when = (row["created_at"] or "")[:10]
    tag = f" [{row['tags']}]" if row["tags"] else ""
    return f"#{row['id']:02d} ({when}){tag} {row['content']}"


def register_notes_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    def _repo() -> NotesRepository:
        return NotesRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        msg = update.effective_message
        if msg is not None:
            await msg.reply_text(text)

    @gate
    async def nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        content = " ".join(context.args).strip()
        if not content:
            await _reply(update, "Uso: /nota <texto>.")
            return
        repo = _repo()
        try:
            note_id = ns.create_note(repo, content)
        finally:
            repo.close()
        await _reply(update, f"Nota #{note_id:02d} salva.")

    @gate
    async def notas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        n = 10
        if context.args:
            try:
                n = int(context.args[0])
            except ValueError:
                pass
        repo = _repo()
        try:
            rows = ns.list_recent(repo, n)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Nenhuma nota.")
            return
        body = "\n".join(_line(r) for r in rows)
        await _reply(update, f"Últimas {len(rows)} notas:\n{body}")

    @gate
    async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        term = " ".join(context.args).strip()
        if not term:
            await _reply(update, "Uso: /buscar <termo>.")
            return
        repo = _repo()
        try:
            rows = ns.search(repo, term)
        finally:
            repo.close()
        if not rows:
            await _reply(update, f"Nada encontrado para \"{term}\".")
            return
        body = "\n".join(_line(r) for r in rows)
        await _reply(update, f"{len(rows)} resultado(s) para \"{term}\":\n{body}")

    for name, fn in [("nota", nota), ("notas", notas), ("buscar", buscar)]:
        application.add_handler(CommandHandler(name, fn))
    log.info("registered notes handlers")
