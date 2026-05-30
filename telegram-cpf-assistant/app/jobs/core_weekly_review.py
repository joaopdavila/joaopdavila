from __future__ import annotations

"""Job domingo 18:00 — revisão semanal consolidada (mesmo conteúdo do /semana)."""

import logging

from app.config import Settings
from app.formatters import split_long_message
from app.jobs.common import send
from app.services import review_service as rs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    text = rs.build_weekly_report(settings.database_path)
    for chunk in split_long_message(text):
        await send(application, settings, chunk)
