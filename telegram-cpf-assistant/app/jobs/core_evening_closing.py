from __future__ import annotations

"""Job 19:30 diário — fechamento do dia, com janela de captura da resposta."""

import logging

from app.config import Settings
from app.jobs.common import send, set_pending
from app.services import health_service as hs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    set_pending(application, settings, "closing")
    await send(application, settings, hs.CLOSING_TEMPLATE)
