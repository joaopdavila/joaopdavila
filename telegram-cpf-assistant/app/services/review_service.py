from __future__ import annotations

"""Revisão semanal consolidada — agrega todos os domínios em um relatório."""

from datetime import date, timedelta
from pathlib import Path

from app.formatters import format_money, today_iso
from app.repositories.finance_repo import FinanceRepository
from app.repositories.garmin_repo import GarminRepository
from app.repositories.health_repo import HealthRepository
from app.repositories.shopping_repo import ShoppingRepository
from app.repositories.tasks_repo import TasksRepository
from app.repositories.wedding_repo import WeddingRepository
from app.services import finance_service as fs
from app.services import garmin_service as gs


def _week_bounds() -> tuple[str, str]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return start.isoformat(), (start + timedelta(days=6)).isoformat()


def build_weekly_report(db_path: Path) -> str:
    start, end = _week_bounds()
    lines = [f"Revisão semanal ({start} a {end})", ""]

    # Tarefas
    tasks = TasksRepository(db_path)
    try:
        pending = tasks.list_pending(limit=50)
        done = tasks.count_done_since(start)
    finally:
        tasks.close()
    lines.append(f"Tarefas: {len(pending)} pendentes, {done} concluídas na semana.")
    for r in list(reversed(pending))[:5]:
        lines.append(f"  #{r['id']:02d} {r['description']}")

    # Compras
    shop = ShoppingRepository(db_path)
    try:
        shop_pending = shop.list_pending()
    finally:
        shop.close()
    if shop_pending:
        itens = ", ".join(r["item"] for r in shop_pending)
        lines.append(f"Compras: {len(shop_pending)} pendentes — {itens}.")
    else:
        lines.append("Compras: lista vazia.")

    # Finanças
    fin = FinanceRepository(db_path)
    try:
        summary = fs.period_summary(fin, "week")
    finally:
        fin.close()
    lines.append(f"Finanças: gasto na semana {format_money(summary['total'])}.")
    for c in summary["by_category"]:
        lines.append(f"  {c['category']}: {format_money(c['total'])}")
    hoje = today_iso()
    if summary["bills_next_7d"]:
        venc = [b for b in summary["bills_next_7d"] if b["due_date"] < hoje]
        prox = [b for b in summary["bills_next_7d"] if b["due_date"] >= hoje]
        if venc:
            lines.append(f"  Contas vencidas: {len(venc)}.")
        if prox:
            lines.append(f"  A vencer (7d): {len(prox)}.")

    # Casamento
    wed = WeddingRepository(db_path)
    try:
        open_count = wed.count_open()
    finally:
        wed.close()
    lines.append(f"Casamento: {open_count} item(ns) em aberto.")

    # Saúde manual
    health = HealthRepository(db_path)
    try:
        checkins = health.checkins_between(start, end)
    finally:
        health.close()
    lines.append(f"Saúde: {len(checkins)}/7 dias com check-in.")

    # Garmin
    garmin = GarminRepository(db_path)
    try:
        lines.append("")
        lines.append(gs.build_weekly_block(garmin))
    finally:
        garmin.close()

    lines.append("")
    lines.append("Plano para a próxima semana? Responda que eu guardo como nota.")
    return "\n".join(lines)
