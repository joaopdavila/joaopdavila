from __future__ import annotations

import sqlite3

from app.repositories.base import BaseRepository


class NotesRepository(BaseRepository):
    def create(self, content: str, tags: str | None = None) -> int:
        return self.insert(
            "INSERT INTO notes (content, tags) VALUES (?, ?)", (content, tags)
        )

    def list_recent(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    def search(self, term: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM notes WHERE content LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (f"%{term}%", limit),
        )
