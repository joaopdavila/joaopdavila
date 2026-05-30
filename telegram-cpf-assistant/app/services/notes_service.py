from __future__ import annotations

"""Regras de negócio de notas."""

import sqlite3

from app.repositories.notes_repo import NotesRepository


def create_note(repo: NotesRepository, content: str, tags: str | None = None) -> int:
    return repo.create(content.strip(), tags)


def list_recent(repo: NotesRepository, n: int = 10) -> list[sqlite3.Row]:
    return repo.list_recent(max(1, min(50, n)))


def search(repo: NotesRepository, term: str) -> list[sqlite3.Row]:
    return repo.search(term.strip())
