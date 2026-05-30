from __future__ import annotations

"""Regras de negócio de finanças (gastos e contas)."""

import sqlite3
from datetime import date, timedelta
from typing import Literal

from app.repositories.finance_repo import FinanceRepository

# Lista canônica sugerida; categorias livres são aceitas (com aviso).
CANONICAL_CATEGORIES = {
    "casa", "alimentação", "alimentacao", "mercado", "transporte",
    "lazer", "casamento", "saúde", "saude", "outros",
}

PayOutcome = Literal["paid", "ambiguous", "not_found"]


def _week_bounds(today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    start = today - timedelta(days=today.weekday())  # segunda
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _month_bounds(today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    start = today.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def add_expense(
    repo: FinanceRepository, amount: float, category: str, description: str
) -> tuple[int, bool]:
    category = category.strip().lower()
    known = category in CANONICAL_CATEGORIES
    expense_id = repo.add_expense(amount, category, description.strip())
    return expense_id, known


def add_bill(
    repo: FinanceRepository, description: str, due_date: str, amount: float | None
) -> int:
    return repo.add_bill(description.strip(), due_date, amount)


def list_pending_bills(repo: FinanceRepository) -> list[sqlite3.Row]:
    return repo.list_pending_bills()


def pay_bill(
    repo: FinanceRepository, term: str, amount: float | None
) -> tuple[PayOutcome, sqlite3.Row | list[sqlite3.Row] | None]:
    matches = repo.find_pending_bill(term.strip())
    if not matches:
        return "not_found", None
    if len(matches) > 1:
        return "ambiguous", matches
    repo.mark_paid(matches[0]["id"], amount)
    return "paid", matches[0]


def period_summary(
    repo: FinanceRepository, scope: Literal["week", "month"]
) -> dict:
    start, end = _week_bounds() if scope == "week" else _month_bounds()
    by_cat = repo.expenses_by_category(start, end)
    total = sum(r["total"] for r in by_cat)
    due_end = (date.today() + timedelta(days=7)).isoformat()
    bills = repo.bills_due_until(due_end)
    return {
        "scope": scope,
        "start": start,
        "end": end,
        "total": total,
        "by_category": by_cat,
        "bills_next_7d": bills,
    }
