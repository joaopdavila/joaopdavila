from __future__ import annotations

"""Helpers compartilhados pelos jobs garmin_*. Sync roda em thread (garminconnect
é bloqueante) para não travar o event loop do bot."""

import asyncio
import logging

from app.clients.garmin_client import GarminClient
from app.config import Settings
from app.repositories.garmin_repo import GarminRepository
from app.services import garmin_service as gs

log = logging.getLogger(__name__)


def make_repo(settings: Settings) -> GarminRepository:
    return GarminRepository(settings.database_path)


async def sync_threaded(settings: Settings, scope: str, days: int = 3) -> dict:
    def _do() -> dict:
        repo = GarminRepository(settings.database_path)
        try:
            client = GarminClient(
                email=settings.garmin_email,
                password=settings.garmin_password,
                token_dir=settings.garmin_token_dir,
            )
            return gs.run_sync(repo, client, scope=scope, days=days)
        finally:
            repo.close()

    return await asyncio.to_thread(_do)


async def send(application, settings: Settings, text: str) -> None:
    try:
        await application.bot.send_message(
            chat_id=settings.telegram_chat_id, text=text
        )
    except Exception:  # noqa: BLE001
        log.exception("failed to send garmin job message")
