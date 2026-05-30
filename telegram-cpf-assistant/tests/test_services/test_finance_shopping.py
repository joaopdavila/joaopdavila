from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app.database import run_migrations
from app.formatters import format_money, parse_due_date, parse_money
from app.repositories.finance_repo import FinanceRepository
from app.repositories.shopping_repo import ShoppingRepository
from app.services import finance_service as fs
from app.services import shopping_service as ss


@pytest.fixture()
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    p = Path(path)
    run_migrations(p)
    yield p
    p.unlink(missing_ok=True)


# ── formatters ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("47.90", 47.90), ("47,90", 47.90), ("1000", 1000.0),
    ("abc", None), ("", None), ("47.999", None),
])
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


def test_format_money():
    assert format_money(1234.5) == "R$ 1.234,50"
    assert format_money(None) == "R$ 0,00"


def test_parse_due_date():
    assert parse_due_date("2026-06-10") == "2026-06-10"
    assert parse_due_date("10/06/2026") == "2026-06-10"
    assert parse_due_date("xx") is None


# ── finance ──────────────────────────────────────────────────────────────────

def test_add_expense_known_and_unknown(db):
    repo = FinanceRepository(db)
    _, known = fs.add_expense(repo, 47.9, "mercado", "pão")
    assert known is True
    _, known2 = fs.add_expense(repo, 10.0, "cripto", "")
    assert known2 is False
    repo.close()


def test_period_summary(db):
    repo = FinanceRepository(db)
    fs.add_expense(repo, 100.0, "mercado", "")
    fs.add_expense(repo, 50.0, "mercado", "")
    fs.add_expense(repo, 30.0, "lazer", "")
    s = fs.period_summary(repo, "week")
    assert s["total"] == 180.0
    cats = {r["category"]: r["total"] for r in s["by_category"]}
    assert cats["mercado"] == 150.0 and cats["lazer"] == 30.0
    repo.close()


def test_bill_pay_flow(db):
    repo = FinanceRepository(db)
    bid = fs.add_bill(repo, "luz", "2026-06-10", 320.0)
    assert len(fs.list_pending_bills(repo)) == 1
    outcome, row = fs.pay_bill(repo, str(bid), 318.5)
    assert outcome == "paid"
    assert fs.list_pending_bills(repo) == []
    repo.close()


# ── shopping ──────────────────────────────────────────────────────────────────

def test_shopping_dedupe(db):
    repo = ShoppingRepository(db)
    o1, _, c1 = ss.add(repo, "leite")
    assert o1 == "added" and c1 == 1
    o2, existing, c2 = ss.add(repo, "Leite")
    assert o2 == "duplicate" and c2 == 1
    repo.close()


def test_shopping_buy_and_clear(db):
    repo = ShoppingRepository(db)
    ss.add(repo, "leite")
    ss.add(repo, "pão")
    outcome, row = ss.mark_bought(repo, "leite")
    assert outcome == "bought"
    assert ss.count_bought(repo) == 1
    removed = ss.clear_bought(repo)
    assert removed == 1
    assert len(ss.list_pending(repo)) == 1
    repo.close()
