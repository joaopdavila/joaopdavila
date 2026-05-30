from __future__ import annotations

import argparse
import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional

from app.config import PROJECT_ROOT, Settings

log = logging.getLogger(__name__)

MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
_MIGRATION_RE = re.compile(r"^(\d+)_.+\.sql$")


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Abre uma conexão SQLite com row factory de dict e foreign keys ligadas."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_schema_version(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    return {int(r["version"]) for r in rows}


def _discover_migrations(migrations_dir: Path) -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        m = _MIGRATION_RE.match(path.name)
        if not m:
            continue
        found.append((int(m.group(1)), path))
    found.sort(key=lambda item: item[0])
    return found


def run_migrations(
    db_path: Path, migrations_dir: Optional[Path] = None
) -> int:
    """Aplica migrations .sql numeradas em ordem; idempotente.

    Retorna a maior versão aplicada após a execução.
    """
    if migrations_dir is None:
        migrations_dir = MIGRATIONS_DIR

    conn = get_connection(db_path)
    try:
        _ensure_schema_version(conn)
        applied = _applied_versions(conn)
        pending = [
            (v, p) for v, p in _discover_migrations(migrations_dir) if v not in applied
        ]
        for version, path in pending:
            log.info("applying migration %03d (%s)", version, path.name)
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
            conn.commit()
        current = max(_applied_versions(conn), default=0)
        log.info("schema_version=%d (%d migration(s) applied)", current, len(pending))
        return current
    finally:
        conn.close()


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="cpf-assistant database tools")
    parser.add_argument(
        "--init", action="store_true", help="create db and apply all migrations"
    )
    args = parser.parse_args(argv)

    settings = Settings.load()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

    if args.init or True:
        version = run_migrations(settings.database_path)
        print(f"db ready at {settings.database_path} (schema_version={version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
