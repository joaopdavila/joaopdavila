from __future__ import annotations

import sqlite3

from app.formatters import now_local
from app.repositories.base import BaseRepository


class ShoppingRepository(BaseRepository):
    def find_pending_by_item(self, item: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM shopping_items WHERE status = 'pending' "
            "AND lower(item) = lower(?)",
            (item,),
        )

    def create(self, item: str) -> int:
        return self.insert(
            "INSERT INTO shopping_items (item) VALUES (?)", (item,)
        )

    def list_pending(self) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM shopping_items WHERE status = 'pending' "
            "ORDER BY created_at ASC"
        )

    def get(self, item_id: int) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM shopping_items WHERE id = ?", (item_id,)
        )

    def find_pending_like(self, term: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM shopping_items WHERE status = 'pending' "
            "AND item LIKE ? ORDER BY created_at ASC",
            (f"%{term}%",),
        )

    def mark_bought(self, item_id: int) -> bool:
        cur = self.execute(
            "UPDATE shopping_items SET status = 'bought', bought_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now_local(), item_id),
        )
        return cur.rowcount > 0

    def count_bought(self) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS n FROM shopping_items WHERE status = 'bought'"
        )
        return int(row["n"]) if row else 0

    def remove_bought(self) -> int:
        cur = self.execute(
            "UPDATE shopping_items SET status = 'removed' WHERE status = 'bought'"
        )
        return cur.rowcount
