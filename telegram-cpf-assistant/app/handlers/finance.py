from __future__ import annotations

"""Handlers do domínio Finanças."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import Settings
from app.formatters import format_money, parse_due_date, parse_money, today_iso
from app.repositories.finance_repo import FinanceRepository
from app.security import authorized_only
from app.services import finance_service as fs

log = logging.getLogger(__name__)


def register_finance_handlers(application: Application, settings: Settings) -> None:
    gate = authorized_only(settings.telegram_chat_id)
    db_path = settings.database_path

    def _repo() -> FinanceRepository:
        return FinanceRepository(db_path)

    async def _reply(update: Update, text: str) -> None:
        msg = update.effective_message
        if msg is not None:
            await msg.reply_text(text)

    @gate
    async def gasto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) < 2:
            await _reply(update, "Uso: /gasto <valor> <categoria> [descrição]. Ex: /gasto 47,90 mercado pão")
            return
        amount = parse_money(context.args[0])
        if amount is None:
            await _reply(update, "Valor inválido. Ex: /gasto 47,90 mercado pão")
            return
        category = context.args[1]
        description = " ".join(context.args[2:])
        repo = _repo()
        try:
            expense_id, known = fs.add_expense(repo, amount, category, description)
        finally:
            repo.close()
        warn = "" if known else " (categoria fora da lista canônica)"
        desc = f" \"{description}\"" if description else ""
        await _reply(
            update,
            f"Gasto #{expense_id} — {format_money(amount)} [{category.lower()}]{desc}{warn}",
        )

    @gate
    async def conta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) < 2:
            await _reply(update, "Uso: /conta <descrição> <vencimento> [valor]. Ex: /conta luz 2026-06-10 320")
            return
        # último arg pode ser valor; penúltimo (ou último) é a data
        args = list(context.args)
        amount = None
        if parse_money(args[-1]) is not None and parse_due_date(args[-1]) is None:
            amount = parse_money(args[-1])
            args = args[:-1]
        due = parse_due_date(args[-1]) if args else None
        if due is None:
            await _reply(update, "Vencimento inválido. Use YYYY-MM-DD, DD/MM ou DD/MM/YYYY.")
            return
        description = " ".join(args[:-1]).strip()
        if not description:
            await _reply(update, "Falta a descrição. Ex: /conta luz 2026-06-10 320")
            return
        repo = _repo()
        try:
            bill_id = fs.add_bill(repo, description, due, amount)
        finally:
            repo.close()
        val = f" — {format_money(amount)}" if amount is not None else ""
        await _reply(update, f"Conta #{bill_id} criada: \"{description}\" vence {due}{val}.")

    @gate
    async def contas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        repo = _repo()
        try:
            rows = fs.list_pending_bills(repo)
        finally:
            repo.close()
        if not rows:
            await _reply(update, "Nenhuma conta pendente.")
            return
        hoje = today_iso()
        lines = []
        for r in rows:
            val = f" {format_money(r['amount'])}" if r["amount"] is not None else ""
            flag = " VENCIDA" if r["due_date"] < hoje else ""
            lines.append(f"#{r['id']:02d} {r['description']} vence {r['due_date']}{val}{flag}")
        await _reply(update, f"Contas pendentes ({len(rows)}):\n" + "\n".join(lines))

    @gate
    async def pago(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await _reply(update, "Uso: /pago <descrição ou id> [valor].")
            return
        args = list(context.args)
        amount = None
        if parse_money(args[-1]) is not None and len(args) > 1:
            amount = parse_money(args[-1])
            args = args[:-1]
        term = " ".join(args).strip()
        repo = _repo()
        try:
            outcome, data = fs.pay_bill(repo, term, amount)
        finally:
            repo.close()
        if outcome == "paid":
            val = f" ({format_money(amount)})" if amount is not None else ""
            await _reply(update, f"Conta paga: \"{data['description']}\"{val}.")
        elif outcome == "ambiguous":
            lst = "\n".join(f"#{r['id']:02d} {r['description']} vence {r['due_date']}" for r in data)
            await _reply(update, f"{len(data)} contas encontradas:\n{lst}\nUse /pago <id> [valor].")
        else:
            await _reply(update, "Conta não encontrada.")

    async def _summary(update: Update, scope: str) -> None:
        repo = _repo()
        try:
            s = fs.period_summary(repo, scope)
        finally:
            repo.close()
        label = "semana" if scope == "week" else "mês"
        lines = [f"Finanças da {label} ({s['start']} a {s['end']}):"]
        lines.append(f"Total gasto: {format_money(s['total'])}")
        for r in s["by_category"]:
            lines.append(f"  {r['category']}: {format_money(r['total'])} ({r['n']}x)")
        if s["bills_next_7d"]:
            lines.append("Contas a vencer (7d):")
            for b in s["bills_next_7d"]:
                val = f" {format_money(b['amount'])}" if b["amount"] is not None else ""
                lines.append(f"  #{b['id']:02d} {b['description']} {b['due_date']}{val}")
        await _reply(update, "\n".join(lines))

    @gate
    async def financas_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _summary(update, "week")

    @gate
    async def financas_mes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _summary(update, "month")

    for name, fn in [
        ("gasto", gasto),
        ("conta", conta),
        ("contas", contas),
        ("pago", pago),
        ("financas_semana", financas_semana),
        ("financas_mes", financas_mes),
    ]:
        application.add_handler(CommandHandler(name, fn))
    log.info("registered finance handlers")
