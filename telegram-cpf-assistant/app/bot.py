from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.handlers.garmin import register_garmin_handlers
from app.scheduler import build_scheduler
from app.security import authorized_only

log = logging.getLogger(__name__)

_START_MONOTONIC = time.monotonic()

HELP_TEXT = (
    "telegram-cpf-assistant — comandos disponíveis nesta fase:\n"
    "/start — inicializa o bot\n"
    "/help — esta mensagem\n"
    "/ping — healthcheck\n"
    "\n"
    "Garmin:\n"
    "/garmin — resumo de hoje (sono, body battery, readiness, último treino)\n"
    "/garmin_sono — detalhe do sono da última noite\n"
    "/garmin_hrv — tendência de HRV dos últimos 7 dias\n"
    "/garmin_treino [id] — último treino (ou específico)\n"
    "/garmin_treinos [n] — últimos N treinos\n"
    "/garmin_corpo — composição corporal + variação\n"
    "/garmin_peso <valor> — registra peso manual\n"
    "/garmin_status — training status + readiness + carga\n"
    "/garmin_semana — resumo semanal Garmin\n"
    "/garmin_sync — força sincronização imediata\n"
    "\n"
    "Comandos previstos (próximas fases):\n"
    "Tarefas: /tarefa /tarefas /tarefas_hoje /tarefas_semana /feito /pendente\n"
    "Notas: /nota /notas /buscar\n"
    "Compras: /comprar /compras /comprado /limpar_compras\n"
    "Finanças: /gasto /conta /contas /pago /financas_semana /financas_mes\n"
    "Casamento: /casamento /casamento_pendencias /casamento_pago /casamento_fornecedor\n"
    "Saúde: /checkin /fechamento /peso /treino /sono /saude_semana\n"
    "Revisão: /semana"
)


def _format_uptime(seconds: int) -> str:
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


async def _post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    scheduler = build_scheduler(application, settings)
    scheduler.start()
    application.bot_data["scheduler"] = scheduler
    log.info("scheduler started")


async def _post_shutdown(application: Application) -> None:
    scheduler = application.bot_data.get("scheduler")
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        log.info("scheduler stopped")


def build_application(settings: Settings) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    gate = authorized_only(settings.telegram_chat_id)

    @gate
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return
        await message.reply_text("Olá. Pronto. /help para ver os comandos.")

    @gate
    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return
        await message.reply_text(HELP_TEXT)

    @gate
    async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return
        uptime = _format_uptime(int(time.monotonic() - _START_MONOTONIC))
        await message.reply_text(f"pong — uptime {uptime}")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ping", ping))

    register_garmin_handlers(application, settings)

    async def error_handler(
        update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        log.exception("unhandled error in handler", exc_info=context.error)
        if not isinstance(update, Update):
            return
        chat = update.effective_chat
        if chat is None or chat.id != settings.telegram_chat_id:
            return
        message = update.effective_message
        if message is None:
            return
        try:
            await message.reply_text("Erro interno, log gravado.")
        except Exception:
            log.exception("failed to send error reply")

    application.add_error_handler(error_handler)
    return application
