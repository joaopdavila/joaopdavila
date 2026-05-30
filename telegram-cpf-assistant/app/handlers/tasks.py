from __future__ import annotations

"""Handlers do domínio Tarefas."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.repositories.tasks_repo import TasksRepository
from app.security import authorized_only
from app.services import tasks_service as ts

log = logging.getLogger(__name__)


def _line(row) -> str:
    due = f" (vence {row['due_date']})" if row["due_date"] else ""
    return f"#{row['id']:02d} {row['description']}{due}"


def register_tasks_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    def _repo() -> TasksRepository:
        return TasksRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        msg = update.effective_message
        if msg is not None:
            await msg.reply_text(text)

    @gate
    async def tarefa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = " ".join(context.args).strip()
        if not text:
            await _reply(update, "Uso: /tarefa <texto>. Ex: /tarefa Renovar CNH 10/06")
            return
        repo = _repo()
        try:
            task_id, due = ts.create_task(repo, text)
            extra = f" (vence {due})" if due else ""
            await _reply(update, f"Tarefa #{task_id:02d} criada{extra}.")
        finally:
            repo.close()

    @gate
    async def tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            rows = ts.list_pending(repo)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Nenhuma tarefa pendente.")
            return
        body = "\n".join(_line(r) for r in rows)
        await _reply(update, f"Tarefas pendentes ({len(rows)}):\n{body}")

    @gate
    async def tarefas_hoje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            rows = ts.list_today(repo)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Nada para hoje.")
            return
        body = "\n".join(_line(r) for r in rows)
        await _reply(update, f"Tarefas de hoje ({len(rows)}):\n{body}")

    @gate
    async def tarefas_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            rows = ts.list_week(repo)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Nenhuma tarefa com vencimento nesta semana.")
            return
        body = "\n".join(_line(r) for r in rows)
        await _reply(update, f"Tarefas da semana ({len(rows)}):\n{body}")

    @gate
    async def feito(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        arg = " ".join(context.args).strip()
        if not arg:
            await _reply(update, "Uso: /feito <id> ou /feito <texto>.")
            return
        repo = _repo()
        try:
            outcome, data = ts.complete(repo, arg)
        finally:
            repo.close()
        if outcome == "done":
            await _reply(update, f"Concluída: \"{data['description']}\".")
        elif outcome == "ambiguous":
            lst = "\n".join(_line(r) for r in data)
            await _reply(update, f"{len(data)} tarefas encontradas:\n{lst}\nUse /feito <id>.")
        else:
            await _reply(update, "Tarefa não encontrada (ou já concluída).")

    @gate
    async def pendente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        arg = " ".join(context.args).strip()
        repo = _repo()
        try:
            task = ts.reopen(repo, arg)
        finally:
            repo.close()
        if task is None:
            await _reply(update, "Uso: /pendente <id> (id válido).")
            return
        await _reply(update, f"Reaberta: \"{task['description']}\".")

    for name, fn in [
        ("tarefa", tarefa),
        ("tarefas", tarefas),
        ("tarefas_hoje", tarefas_hoje),
        ("tarefas_semana", tarefas_semana),
        ("feito", feito),
        ("pendente", pendente),
    ]:
        application.add_handler(CommandHandler(name, fn))
    log.info("registered tasks handlers")
