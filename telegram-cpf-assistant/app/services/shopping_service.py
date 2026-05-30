from __future__ import annotations

"""Regras de negócio de compras."""

import sqlite3
from typing import Literal

from app.repositories.shopping_repo import ShoppingRepository

AddOutcome = Literal["added", "duplicate"]
BuyOutcome = Literal["bought", "ambiguous", "not_found"]


def add(repo: ShoppingRepository, item: str) -> tuple[AddOutcome, sqlite3.Row | int, int]:
    item = item.strip()
    existing = repo.find_pending_by_item(item)
    if existing is not None:
        return "duplicate", existing, len(repo.list_pending())
    item_id = repo.create(item)
    return "added", item_id, len(repo.list_pending())


def list_pending(repo: ShoppingRepository) -> list[sqlite3.Row]:
    return repo.list_pending()


def mark_bought(
    repo: ShoppingRepository, arg: str
) -> tuple[BuyOutcome, sqlite3.Row | list[sqlite3.Row] | None]:
    arg = arg.strip()
    if arg.isdigit():
        row = repo.get(int(arg))
        if row is None or row["status"] != "pending":
            return "not_found", None
        repo.mark_bought(row["id"])
        return "bought", row
    matches = repo.find_pending_like(arg)
    if not matches:
        return "not_found", None
    if len(matches) > 1:
        return "ambiguous", matches
    repo.mark_bought(matches[0]["id"])
    return "bought", matches[0]


def count_bought(repo: ShoppingRepository) -> int:
    return repo.count_bought()


def clear_bought(repo: ShoppingRepository) -> int:
    return repo.remove_bought()
