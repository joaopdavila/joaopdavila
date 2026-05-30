from __future__ import annotations

"""Handlers de check-in matinal e fechamento diário, com captura de resposta
livre em janela de 2h (estado em memória)."""

import logging
import time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.repositories.garmin_repo import GarminRepository
from app.repositories.health_repo import HealthRepository
from app.security import authorized_only
from app.services import health_service as hs

log = logging.getLogger(__name__)

_WINDOW = 2 * 3600  # 2h para responder ao template


def _garmin_context(db_path) -> tuple[str | None, float | None]:
    """Linha de contexto Garmin para o check-in + horas de sono p/ pré-preencher."""
    repo = GarminRepository(db_path)
    try:
        sleep = repo.latest_sleep()
        training = repo.latest_training()
    except Exception:  # noqa: BLE001 — tabelas garmin podem não existir
        return None, None
    finally:
        repo.close()
    parts = []
    sleep_hours = None
    if sleep:
        sleep_hours = sleep["total_hours"]
        h = f"dormiu {sleep['total_hours']}h" if sleep["total_hours"] else None
        if sleep["hrv_avg"] is not None:
            h = (h + f", HRV {sleep['hrv_avg']} ms") if h else f"HRV {sleep['hrv_avg']} ms"
        if h:
            parts.append(h)
    if training and training["readiness_score"] is not None:
        parts.append(f"readiness {training['readiness_score']}/100")
    line = ("Contexto Garmin: " + ", ".join(parts) + ".") if parts else None
    return line, sleep_hours


def register_health_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path
    application.bot_data.setdefault("pending_response", {})

    def _repo() -> HealthRepository:
        return HealthRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        msg = update.effective_message
        if msg is not None:
            await msg.reply_text(text)

    def _set_pending(context, chat_id, kind) -> None:
        context.application.bot_data["pending_response"][chat_id] = (
            kind,
            time.monotonic() + _WINDOW,
        )

    @gate
    async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        line, sleep_hours = _garmin_context(db_path)
        if sleep_hours is not None:
            repo = _repo()
            try:
                hs.save_checkin(repo, {"sleep_hours": sleep_hours})
            finally:
                repo.close()
        template = hs.CHECKIN_TEMPLATE
        if line:
            template = f"{line}\n\n{template}"
        _set_pending(context, update.effective_chat.id, "checkin")
        await _reply(update, template)

    @gate
    async def fechamento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _set_pending(context, update.effective_chat.id, "closing")
        await _reply(update, hs.CLOSING_TEMPLATE)

    @gate
    async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        pending = context.application.bot_data.get("pending_response", {})
        entry = pending.get(chat_id)
        if entry is None:
            return
        kind, expiry = entry
        if time.monotonic() > expiry:
            pending.pop(chat_id, None)
            return
        text = update.effective_message.text or ""
        repo = _repo()
        try:
            if kind == "checkin":
                fields = hs.parse_checkin(text)
                hs.save_checkin(repo, fields)
                pending.pop(chat_id, None)
                prio = fields.get("priority")
                extra = f" Prioridade: \"{prio}\"." if prio else ""
                await _reply(update, f"Check-in registrado.{extra}")
            else:
                fields = hs.parse_closing(text)
                hs.save_closing(repo, fields)
                pending.pop(chat_id, None)
                await _reply(update, "Fechamento registrado.")
        finally:
            repo.close()

    @gate
    async def peso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await _reply(update, "Uso: /peso <valor>. Ex: /peso 84.2")
            return
        try:
            value = float(context.args[0].replace(",", "."))
        except ValueError:
            await _reply(update, "Valor inválido. Ex: /peso 84.2")
            return
        repo = _repo()
        try:
            hs.save_weight(repo, value)
        finally:
            repo.close()
        await _reply(update, f"Peso registrado: {value:.1f} kg.")

    @gate
    async def treino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = " ".join(context.args).strip()
        if not text:
            await _reply(update, "Uso: /treino <texto>. Ex: /treino corrida 6km")
            return
        repo = _repo()
        try:
            hs.save_workout(repo, text)
        finally:
            repo.close()
        await _reply(update, "Treino registrado.")

    @gate
    async def sono(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = " ".join(context.args).strip()
        if not text:
            await _reply(update, "Uso: /sono <horas ou texto>. Ex: /sono 7.5")
            return
        repo = _repo()
        try:
            hs.save_sleep(repo, text)
        finally:
            repo.close()
        await _reply(update, "Sono registrado.")

    @gate
    async def saude_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        garmin_repo = GarminRepository(db_path)
        try:
            text = hs.week_summary(repo, garmin_repo)
        finally:
            repo.close()
            garmin_repo.close()
        await _reply(update, text)

    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("fechamento", fechamento))
    application.add_handler(CommandHandler("peso", peso))
    application.add_handler(CommandHandler("treino", treino))
    application.add_handler(CommandHandler("sono", sono))
    application.add_handler(CommandHandler("saude_semana", saude_semana))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_text))
    log.info("registered health handlers")
