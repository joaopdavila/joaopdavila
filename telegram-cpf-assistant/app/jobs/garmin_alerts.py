from __future__ import annotations

"""Job 08:00 / 14:00 / 20:00 — alertas reativos (porte de alerts.py).
Sincroniza e checa HRV em queda, sono curto e body battery baixa. Só envia
mensagem se alguma condição disparar — silêncio = tudo normal."""

import logging

from app.config import Settings
from app.jobs.garmin_common import make_repo, send, sync_threaded
from app.services import garmin_service as gs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    await sync_threaded(settings, scope="alerts", days=3)
    repo = make_repo(settings)
    try:
        alerts = gs.check_alerts(repo)
    finally:
        repo.close()
    if not alerts:
        log.info("garmin_alerts: nenhum alerta — tudo normal")
        return
    text = "Alerta Garmin:\n" + "\n".join(f"- {a}" for a in alerts)
    await send(application, settings, text)
