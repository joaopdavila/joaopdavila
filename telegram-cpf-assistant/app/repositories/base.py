from __future__ import annotations

import sqlite3
from pathlib import Path

from app.database import get_connection


class BaseRepository:
    """Base de repositórios: SQL cru parametrizado sobre uma conexão SQLite.

    Mantém uma única conexão por repositório. Sem ORM — os métodos de domínio
    nas subclasses retornam `sqlite3.Row` (acesso por nome de coluna) ou
    dataclasses montadas a partir dele.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── helpers ────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def insert(self, sql: str, params: tuple = ()) -> int:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return int(cur.lastrowid)
