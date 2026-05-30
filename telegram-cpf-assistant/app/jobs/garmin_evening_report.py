from __future__ import annotations

"""Job 19:00 — recap do dia (passos, kcal, stress, treino). Sincroniza o dia
corrente antes de ler, pois o sync matinal não tem os dados de hoje. Antecede o
/fechamento 19:30."""

import logging

from app.config import Settings
from app.jobs.garmin_common import make_repo, send, sync_threaded
from app.services import garmin_service as gs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    await sync_threaded(settings, scope="evening", days=1)
    repo = make_repo(settings)
    try:
        text = gs.build_evening_report(repo)
    finally:
        repo.close()
    await send(application, settings, text)
