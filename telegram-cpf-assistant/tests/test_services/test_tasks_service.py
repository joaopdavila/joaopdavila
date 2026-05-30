from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app.database import run_migrations
from app.repositories.tasks_repo import TasksRepository
from app.services import tasks_service as ts


@pytest.fixture()
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Path(path)
    run_migrations(db)
    r = TasksRepository(db)
    yield r
    r.close()
    db.unlink(missing_ok=True)


def test_create_and_list(repo):
    tid, due = ts.create_task(repo, "Renovar CNH")
    assert tid == 1 and due is None
    pending = ts.list_pending(repo)
    assert len(pending) == 1
    assert pending[0]["description"] == "Renovar CNH"


def test_create_with_due_date(repo):
    _, due = ts.create_task(repo, "Pagar luz 10/06/2026")
    assert due == "2026-06-10"


def test_complete_by_id(repo):
    tid, _ = ts.create_task(repo, "Comprar pão")
    outcome, row = ts.complete(repo, str(tid))
    assert outcome == "done"
    assert row["description"] == "Comprar pão"
    assert ts.list_pending(repo) == []


def test_complete_by_text_unique(repo):
    ts.create_task(repo, "Renovar CNH")
    outcome, row = ts.complete(repo, "cnh")
    assert outcome == "done"


def test_complete_ambiguous(repo):
    ts.create_task(repo, "Renovar CNH")
    ts.create_task(repo, "Renovar plano celular")
    outcome, rows = ts.complete(repo, "renovar")
    assert outcome == "ambiguous"
    assert len(rows) == 2


def test_complete_not_found(repo):
    outcome, _ = ts.complete(repo, "999")
    assert outcome == "not_found"


def test_reopen(repo):
    tid, _ = ts.create_task(repo, "Tarefa X")
    ts.complete(repo, str(tid))
    row = ts.reopen(repo, str(tid))
    assert row["status"] == "pending"
    assert len(ts.list_pending(repo)) == 1
