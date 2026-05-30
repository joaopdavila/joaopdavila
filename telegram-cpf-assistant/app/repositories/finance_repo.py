from __future__ import annotations

import sqlite3

from app.formatters import now_local
from app.repositories.base import BaseRepository


class FinanceRepository(BaseRepository):
    # ── expenses ────────────────────────────────────────────────────────────

    def add_expense(self, amount: float, category: str, description: str) -> int:
        return self.insert(
            "INSERT INTO expenses (amount, category, description) VALUES (?, ?, ?)",
            (amount, category, description),
        )

    def expenses_between(self, start: str, end: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM expenses WHERE expense_date BETWEEN ? AND ? "
            "ORDER BY expense_date DESC",
            (start, end),
        )

    def expenses_by_category(self, start: str, end: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS n FROM expenses "
            "WHERE expense_date BETWEEN ? AND ? GROUP BY category "
            "ORDER BY total DESC",
            (start, end),
        )

    # ── bills ──────────────────────────────────────────────────────────────

    def add_bill(self, description: str, due_date: str, amount: float | None) -> int:
        return self.insert(
            "INSERT INTO bills (description, due_date, amount) VALUES (?, ?, ?)",
            (description, due_date, amount),
        )

    def list_pending_bills(self) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM bills WHERE status IN ('pending', 'overdue') "
            "ORDER BY due_date ASC"
        )

    def bills_due_until(self, end: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM bills WHERE status IN ('pending', 'overdue') "
            "AND due_date <= ? ORDER BY due_date ASC",
            (end,),
        )

    def find_pending_bill(self, term: str) -> list[sqlite3.Row]:
        if term.isdigit():
            row = self.query_one(
                "SELECT * FROM bills WHERE id = ? AND status != 'paid'", (int(term),)
            )
            return [row] if row else []
        return self.query_all(
            "SELECT * FROM bills WHERE status != 'paid' AND description LIKE ? "
            "ORDER BY due_date ASC",
            (f"%{term}%",),
        )

    def mark_paid(self, bill_id: int, paid_amount: float | None) -> bool:
        cur = self.execute(
            "UPDATE bills SET status = 'paid', paid_at = ?, paid_amount = ?, "
            "updated_at = ? WHERE id = ?",
            (now_local(), paid_amount, now_local(), bill_id),
        )
        return cur.rowcount > 0
