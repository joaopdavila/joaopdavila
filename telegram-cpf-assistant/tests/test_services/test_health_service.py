from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app.database import run_migrations
from app.repositories.health_repo import HealthRepository
from app.services import health_service as hs


@pytest.fixture()
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    p = Path(path)
    run_migrations(p)
    r = HealthRepository(p)
    yield r
    r.close()
    p.unlink(missing_ok=True)


def test_parse_checkin_bullets():
    fields = hs.parse_checkin("1. fechar deck Q2\n2. corrida 5km\n3. pagar luz\n4. -")
    assert fields["priority"] == "fechar deck Q2"
    assert fields["workout"] == "corrida 5km"
    assert "fechar deck" in fields["raw_response"]


def test_parse_closing_yesno():
    fields = hs.parse_closing("1. sim\n2. não\n3. sim\n4. revisar contrato")
    assert fields["main_task_done"] == 1
    assert fields["had_relevant_expense"] == 0
    assert fields["health_done"] == 1
    assert fields["tomorrow_pending"] == "revisar contrato"


def test_save_checkin_upsert(repo):
    hs.save_checkin(repo, {"sleep_hours": 7.0}, "2026-05-30")
    hs.save_checkin(repo, {"priority": "x", "raw_response": "1. x"}, "2026-05-30")
    row = repo.get_checkin("2026-05-30")
    # upsert com COALESCE preserva sleep_hours e adiciona priority
    assert row["sleep_hours"] == 7.0
    assert row["priority"] == "x"


def test_save_closing(repo):
    hs.save_closing(repo, hs.parse_closing("1. sim\n4. nada"), "2026-05-30")
    row = repo.get_closing("2026-05-30")
    assert row["main_task_done"] == 1
    assert row["tomorrow_pending"] == "nada"
