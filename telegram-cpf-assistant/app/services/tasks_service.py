from __future__ import annotations

"""Regras de negócio de tarefas. Sem Telegram, sem SQL direto."""

import sqlite3
from typing import Literal

from app.formatters import parse_due_date
from app.repositories.tasks_repo import TasksRepository

CompleteOutcome = Literal["done", "ambiguous", "not_found", "invalid"]


def create_task(repo: TasksRepository, text: str) -> tuple[int, str | None]:
    """Cria tarefa. Se o fim do texto for uma data, vira due_date."""
    text = text.strip()
    due_date = None
    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        maybe = parse_due_date(parts[1])
        if maybe:
            text, due_date = parts[0].strip(), maybe
    task_id = repo.create(text, due_date)
    return task_id, due_date


def list_pending(repo: TasksRepository) -> list[sqlite3.Row]:
    return repo.list_pending()


def list_today(repo: TasksRepository) -> list[sqlite3.Row]:
    return repo.list_today()


def list_week(repo: TasksRepository) -> list[sqlite3.Row]:
    return repo.list_week()


def complete(
    repo: TasksRepository, arg: str
) -> tuple[CompleteOutcome, sqlite3.Row | list[sqlite3.Row] | None]:
    arg = arg.strip()
    if not arg:
        return "invalid", None
    if arg.isdigit():
        task = repo.get(int(arg))
        if task is None or task["status"] != "pending":
            return "not_found", None
        repo.set_status(task["id"], "done")
        return "done", task
    matches = repo.search_pending(arg)
    if not matches:
        return "not_found", None
    if len(matches) > 1:
        return "ambiguous", matches
    repo.set_status(matches[0]["id"], "done")
    return "done", matches[0]


def reopen(repo: TasksRepository, arg: str) -> sqlite3.Row | None:
    if not arg.strip().isdigit():
        return None
    task = repo.get(int(arg))
    if task is None:
        return None
    repo.set_status(task["id"], "pending")
    return repo.get(task["id"])
