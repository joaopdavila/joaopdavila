from __future__ import annotations

"""Job 07:30 — relatório matinal Garmin (lê do SQLite). Antecede o /checkin 08:00."""

import logging

from app.config import Settings
from app.jobs.garmin_common import make_repo, send
from app.services import garmin_service as gs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    repo = make_repo(settings)
    try:
        text = gs.build_morning_report(repo)
    finally:
        repo.close()
    await send(application, settings, text)
