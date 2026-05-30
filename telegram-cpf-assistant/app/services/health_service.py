from __future__ import annotations

"""Regras de negócio de check-in matinal e fechamento diário.

O estado "aguardando resposta" vive em memória no handler; aqui ficam só o
parsing do texto livre e a persistência."""

import re
from datetime import date, timedelta

from app.formatters import today_iso
from app.repositories.health_repo import HealthRepository

CHECKIN_TEMPLATE = (
    "Check-in rápido:\n"
    "1. Prioridade pessoal de hoje:\n"
    "2. Treino planejado:\n"
    "3. Alguma pendência crítica?\n"
    "4. Algum pagamento ou tarefa da casa?\n"
    "\n"
    "Responda em uma mensagem (pode usar os números)."
)

CLOSING_TEMPLATE = (
    "Fechamento do dia:\n"
    "1. Tarefa principal concluída? (sim/não)\n"
    "2. Teve gasto relevante? (sim/não)\n"
    "3. Cuidou da saúde hoje? (sim/não)\n"
    "4. O que fica pendente para amanhã?\n"
    "\n"
    "Responda em uma mensagem (pode usar os números)."
)

_BULLET_RE = re.compile(r"^\s*(\d)\s*[\.\)\-:]\s*(.+)$")
_YES = {"sim", "s", "yes", "y", "1", "ok", "feito"}
_NO = {"não", "nao", "n", "no", "0", "-"}


def _bullets(text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for line in text.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def _yesno(value: str | None) -> int | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in _YES:
        return 1
    if v in _NO:
        return 0
    return None


def parse_checkin(text: str) -> dict:
    bullets = _bullets(text)
    return {
        "priority": bullets.get(1),
        "workout": bullets.get(2),
        "raw_response": text.strip(),
    }


def parse_closing(text: str) -> dict:
    bullets = _bullets(text)
    return {
        "main_task_done": _yesno(bullets.get(1)),
        "had_relevant_expense": _yesno(bullets.get(2)),
        "health_done": _yesno(bullets.get(3)),
        "tomorrow_pending": bullets.get(4),
        "raw_response": text.strip(),
    }


def save_checkin(repo: HealthRepository, fields: dict, checkin_date: str | None = None) -> None:
    repo.upsert_checkin(checkin_date or today_iso(), fields)


def save_closing(repo: HealthRepository, fields: dict, closing_date: str | None = None) -> None:
    repo.upsert_closing(closing_date or today_iso(), fields)


# ── saúde manual estendida (Fase 7) ─────────────────────────────────────────

def save_weight(repo: HealthRepository, weight_kg: float) -> None:
    repo.upsert_checkin(today_iso(), {"weight_kg": round(weight_kg, 2)})


def save_workout(repo: HealthRepository, text: str) -> None:
    repo.upsert_checkin(today_iso(), {"workout": text.strip()})


def save_sleep(repo: HealthRepository, raw: str) -> None:
    raw = raw.strip()
    try:
        hours = float(raw.replace(",", "."))
        repo.upsert_checkin(today_iso(), {"sleep_hours": hours})
    except ValueError:
        repo.upsert_checkin(today_iso(), {"sleep_note": raw})


def week_summary(repo: HealthRepository, garmin_repo=None) -> str:
    """Resumo de saúde da semana. Garmin é fonte primária; manual é fallback."""
    today = date.today()
    start = (today - timedelta(days=today.weekday())).isoformat()
    end = (today - timedelta(days=today.weekday()) + timedelta(days=6)).isoformat()
    checkins = repo.checkins_between(start, end)

    weights = [c["weight_kg"] for c in checkins if c["weight_kg"] is not None]
    sleeps = [c["sleep_hours"] for c in checkins if c["sleep_hours"] is not None]
    workouts = [c["workout"] for c in checkins if c["workout"]]

    # fallback/primário Garmin
    g_sleep, g_weight = None, None
    if garmin_repo is not None:
        try:
            grows = garmin_repo.list_sleep(7)
            gvals = [r["total_hours"] for r in grows if r["total_hours"] is not None]
            if gvals:
                g_sleep = sum(gvals) / len(gvals)
            body = garmin_repo.latest_body()
            if body and body["weight_kg"] is not None:
                g_weight = body["weight_kg"]
        except Exception:  # noqa: BLE001
            pass

    lines = [f"Saúde da semana ({start} a {end}):"]
    lines.append(f"Dias com check-in: {len(checkins)}/7")
    if g_weight is not None:
        lines.append(f"Peso (Garmin): {g_weight} kg")
    elif weights:
        lines.append(f"Peso (manual): {weights[-1]} kg")
    if g_sleep is not None:
        lines.append(f"Sono médio (Garmin): {g_sleep:.1f}h")
    elif sleeps:
        lines.append(f"Sono médio (manual): {sum(sleeps) / len(sleeps):.1f}h")
    lines.append(f"Treinos registrados: {len(workouts)}")
    return "\n".join(lines)
