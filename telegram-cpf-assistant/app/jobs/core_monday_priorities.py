from __future__ import annotations

"""Job segunda 08:05 — pergunta as 3 prioridades da semana (após o check-in)."""

import logging

from app.config import Settings
from app.jobs.common import send

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    await send(
        application,
        settings,
        "Prioridades da semana? Liste o top 3 e crie com /tarefa cada uma.",
    )
