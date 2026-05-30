from __future__ import annotations

"""Job sexta 17:30 — fechamento financeiro da semana (apenas leitura)."""

import logging

from app.config import Settings
from app.formatters import format_money, today_iso
from app.jobs.common import send
from app.repositories.finance_repo import FinanceRepository
from app.services import finance_service as fs

log = logging.getLogger(__name__)


async def run(application, settings: Settings) -> None:
    repo = FinanceRepository(settings.database_path)
    try:
        summary = fs.period_summary(repo, "week")
    finally:
        repo.close()
    lines = [f"Fechamento financeiro da semana: {format_money(summary['total'])} gastos."]
    hoje = today_iso()
    prox = [b for b in summary["bills_next_7d"] if b["due_date"] >= hoje]
    if prox:
        lines.append(f"Contas a vencer nos próximos 7 dias: {len(prox)}.")
        for b in prox:
            val = f" {format_money(b['amount'])}" if b["amount"] is not None else ""
            lines.append(f"  {b['description']} ({b['due_date']}){val}")
    await send(application, settings, "\n".join(lines))
