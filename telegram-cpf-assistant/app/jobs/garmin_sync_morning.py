from __future__ import annotations

"""Job 06:30 — puxa dados Garmin (noite anterior + dia) e grava no SQLite.
Job de dados, sem envio de mensagem."""

import logging

from app.config import Settings
from app.jobs.garmin_common import sync_threaded

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    counts = await sync_threaded(settings, scope="morning", days=3)
    log.info("garmin_sync_morning: %s", counts)
