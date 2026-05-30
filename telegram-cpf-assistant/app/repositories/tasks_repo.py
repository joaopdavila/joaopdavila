from __future__ import annotations

import sqlite3

from app.formatters import now_local
from app.repositories.base import BaseRepository


class TasksRepository(BaseRepository):
    def create(self, description: str, due_date: str | None) -> int:
        return self.insert(
            "INSERT INTO tasks (description, due_date) VALUES (?, ?)",
            (description, due_date),
        )

    def get(self, task_id: int) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))

    def list_pending(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM tasks WHERE status = 'pending' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def list_today(self) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM tasks WHERE status = 'pending' "
            "AND (due_date = ? OR due_date IS NULL) "
            "ORDER BY due_date IS NULL, due_date ASC, created_at DESC",
            (self._today(),),
        )

    def list_week(self) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM tasks WHERE status = 'pending' "
            "AND due_date IS NOT NULL AND due_date BETWEEN ? AND ? "
            "ORDER BY due_date ASC",
            (self._today(), self._week_end()),
        )

    def search_pending(self, term: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM tasks WHERE status = 'pending' AND description LIKE ? "
            "ORDER BY created_at DESC",
            (f"%{term}%",),
        )

    def set_status(self, task_id: int, status: str) -> bool:
        completed = now_local() if status == "done" else None
        cur = self.execute(
            "UPDATE tasks SET status = ?, completed_at = ?, updated_at = ? "
            "WHERE id = ?",
            (status, completed, now_local(), task_id),
        )
        return cur.rowcount > 0

    def count_done_since(self, start_date: str) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS n FROM tasks WHERE status = 'done' "
            "AND completed_at >= ?",
            (start_date,),
        )
        return int(row["n"]) if row else 0

    @staticmethod
    def _today() -> str:
        from app.formatters import today_iso

        return today_iso()

    @staticmethod
    def _week_end() -> str:
        from datetime import date, timedelta

        return (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
