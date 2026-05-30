from __future__ import annotations

"""Handlers dos comandos /garmin*. Leem do SQLite; só /garmin_sync chama a API
(em thread separada, para não bloquear o event loop)."""

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.clients.garmin_client import GarminClient
from app.config import Settings
from app.repositories.garmin_repo import GarminRepository
from app.security import authorized_only
from app.services import garmin_service as gs

log = logging.getLogger(__name__)


def _parse_money(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def register_garmin_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    def _repo() -> GarminRepository:
        return GarminRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        message = update.effective_message
        if message is not None:
            await message.reply_text(text)

    @gate
    async def garmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            await _reply(update, gs.format_today(repo))
        finally:
            repo.close()

    @gate
    async def garmin_sono(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            await _reply(update, gs.format_sleep(repo))
        finally:
            repo.close()

    @gate
    async def garmin_hrv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            await _reply(update, gs.format_hrv(repo))
        finally:
            repo.close()

    @gate
    async def garmin_treino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        activity_id = context.args[0] if context.args else None
        repo = _repo()
        try:
            await _reply(update, gs.format_workout(repo, activity_id))
        finally:
            repo.close()

    @gate
    async def garmin_treinos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        n = 7
        if context.args:
            try:
                n = max(1, min(30, int(context.args[0])))
            except ValueError:
                pass
        repo = _repo()
        try:
            await _reply(update, gs.format_workouts(repo, n))
        finally:
            repo.close()

    @gate
    async def garmin_corpo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            await _reply(update, gs.format_body(repo))
        finally:
            repo.close()

    @gate
    async def garmin_peso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await _reply(update, "Uso: /garmin_peso <valor>. Exemplo: /garmin_peso 84.2")
            return
        value = _parse_money(context.args[0])
        if value is None or value <= 0:
            await _reply(update, "Valor inválido. Exemplo: /garmin_peso 84.2")
            return
        repo = _repo()
        try:
            gs.add_manual_weight(repo, value)
            await _reply(update, f"Peso registrado: {value:.1f} kg (fonte manual).")
        finally:
            repo.close()

    @gate
    async def garmin_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            await _reply(update, gs.format_status(repo))
        finally:
            repo.close()

    @gate
    async def garmin_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            await _reply(update, gs.format_week(repo))
        finally:
            repo.close()

    @gate
    async def garmin_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _reply(update, "Sincronizando com o Garmin...")

        def _do_sync() -> dict:
            repo = GarminRepository(db_path)
            try:
                client = GarminClient(
                    email=settings.garmin_email,
                    password=settings.garmin_password,
                    token_dir=settings.garmin_token_dir,
                )
                return gs.run_sync(repo, client, scope="manual", days=3)
            finally:
                repo.close()

        counts = await asyncio.to_thread(_do_sync)
        repo = _repo()
        try:
            status = gs.format_sync_status(repo)
        finally:
            repo.close()
        await _reply(
            update,
            "Sync concluído: "
            + ", ".join(f"{k}={v}" for k, v in counts.items())
            + f"\n{status}",
        )

    handlers = [
        ("garmin", garmin),
        ("garmin_sono", garmin_sono),
        ("garmin_hrv", garmin_hrv),
        ("garmin_treino", garmin_treino),
        ("garmin_treinos", garmin_treinos),
        ("garmin_corpo", garmin_corpo),
        ("garmin_peso", garmin_peso),
        ("garmin_status", garmin_status),
        ("garmin_semana", garmin_semana),
        ("garmin_sync", garmin_sync),
    ]
    for name, fn in handlers:
        application.add_handler(CommandHandler(name, fn))
    log.info("registered %d garmin command handlers", len(handlers))
