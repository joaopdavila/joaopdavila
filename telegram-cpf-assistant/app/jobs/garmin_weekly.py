from __future__ import annotations

"""Job domingo 17:55 — bloco semanal Garmin (entra antes da /semana das 18:00)."""

import logging

from app.config import Settings
from app.jobs.garmin_common import make_repo, send, sync_threaded
from app.services import garmin_service as gs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    await sync_threaded(settings, scope="weekly", days=7)
    repo = make_repo(settings)
    try:
        text = gs.build_weekly_block(repo)
    finally:
        repo.close()
    await send(application, settings, text)
