from __future__ import annotations

"""Job 08:00 diário — check-in matinal. Inclui contexto Garmin se houver e
abre janela de captura da resposta livre."""

import logging

from app.config import Settings
from app.handlers.health import _garmin_context
from app.jobs.common import send, set_pending
from app.repositories.health_repo import HealthRepository
from app.services import health_service as hs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    line, sleep_hours = _garmin_context(settings.database_path)
    if sleep_hours is not None:
        repo = HealthRepository(settings.database_path)
        try:
            hs.save_checkin(repo, {"sleep_hours": sleep_hours})
        finally:
            repo.close()
    template = hs.CHECKIN_TEMPLATE
    if line:
        template = f"Bom dia. {line}\n\n{template}"
    set_pending(application, settings, "checkin")
    await send(application, settings, template)
