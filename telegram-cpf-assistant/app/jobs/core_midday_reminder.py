from __future__ import annotations

"""Job 12:30 (dias úteis) — lembrete leve do meio-dia."""

import logging

from app.config import Settings
from app.jobs.common import send

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    await send(
        application,
        settings,
        "Água e almoço leve. Tudo no rumo? Use /tarefas_hoje para revisar o dia.",
    )
