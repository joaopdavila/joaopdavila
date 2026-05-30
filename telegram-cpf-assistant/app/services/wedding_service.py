from __future__ import annotations

"""Regras de negócio do domínio Casamento."""

import sqlite3

from app.repositories.wedding_repo import WeddingRepository


def add_pendencia(repo: WeddingRepository, description: str) -> int:
    return repo.create("pendencia", description.strip())


def list_pendencias(repo: WeddingRepository) -> list[sqlite3.Row]:
    return repo.list_open("pendencia")


def register_payment(
    repo: WeddingRepository, description: str, amount: float | None
) -> int:
    return repo.create("pagamento", description.strip(), amount=amount, status="done")


def register_vendor(repo: WeddingRepository, vendor: str, note: str) -> int:
    return repo.create("fornecedor", note.strip(), vendor=vendor.strip())


def open_items(repo: WeddingRepository) -> list[sqlite3.Row]:
    return repo.list_open()
