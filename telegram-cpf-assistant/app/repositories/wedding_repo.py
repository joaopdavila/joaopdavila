from __future__ import annotations

import sqlite3

from app.formatters import now_local
from app.repositories.base import BaseRepository


class WeddingRepository(BaseRepository):
    def create(
        self,
        kind: str,
        description: str,
        vendor: str | None = None,
        amount: float | None = None,
        status: str = "open",
    ) -> int:
        return self.insert(
            "INSERT INTO wedding_items (kind, description, vendor, amount, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (kind, description, vendor, amount, status),
        )

    def list_open(self, kind: str | None = None) -> list[sqlite3.Row]:
        if kind:
            return self.query_all(
                "SELECT * FROM wedding_items WHERE status = 'open' AND kind = ? "
                "ORDER BY created_at ASC",
                (kind,),
            )
        return self.query_all(
            "SELECT * FROM wedding_items WHERE status = 'open' "
            "ORDER BY kind, created_at ASC"
        )

    def list_by_kind(self, kind: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM wedding_items WHERE kind = ? ORDER BY created_at DESC",
            (kind,),
        )

    def mark_done(self, item_id: int) -> bool:
        cur = self.execute(
            "UPDATE wedding_items SET status = 'done', updated_at = ? WHERE id = ?",
            (now_local(), item_id),
        )
        return cur.rowcount > 0

    def count_open(self) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS n FROM wedding_items WHERE status = 'open'"
        )
        return int(row["n"]) if row else 0
