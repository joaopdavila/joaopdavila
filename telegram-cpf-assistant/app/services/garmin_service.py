from __future__ import annotations

"""
Garmin service — orquestra busca (client) + persistência (repo) + formatação.

Regras:
- Sync (jobs) chama o client (API live) e grava no SQLite.
- Handlers leem SEMPRE do SQLite (nunca chamam a API no caminho síncrono).
- Mensagens em PT-BR seco: sem emoji, sem Markdown.

Parsers portados de joaopdavila/garmin-dashboard/daily_summary.py.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.clients.garmin_client import GarminClient
from app.repositories.garmin_repo import GarminRepository

log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _date_offset(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v) -> Optional[int]:
    n = _num(v)
    return int(round(n)) if n is not None else None


def _get(d, *path):
    cur = d
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _first(d):
    if isinstance(d, list):
        return d[0] if d else None
    return d


def _hours(seconds) -> Optional[float]:
    s = _num(seconds)
    return round(s / 3600, 2) if s else None


def _hm(hours: Optional[float]) -> str:
    if hours is None:
        return "—"
    h = int(hours)
    m = int(round((hours - h) * 60))
    return f"{h}h{m:02d}"


# ── parsers (API JSON → dict de colunas) ───────────────────────────────────────

def parse_daily(raw: dict) -> dict:
    dist_m = _num(raw.get("totalDistanceMeters"))
    return {
        "steps": _int(raw.get("totalSteps")),
        "calories_total": _int(raw.get("totalKilocalories")),
        "calories_active": _int(raw.get("activeKilocalories")),
        "distance_km": round(dist_m / 1000, 2) if dist_m else None,
        "resting_hr": _int(raw.get("restingHeartRate")),
        "body_battery_max": _int(raw.get("bodyBatteryHighestValue")),
        "body_battery_min": _int(raw.get("bodyBatteryLowestValue")),
        "stress_avg": _int(raw.get("averageStressLevel")),
    }


def parse_sleep(raw: dict, hrv_raw: Optional[dict]) -> dict:
    dto = raw.get("dailySleepDTO") or {}
    return {
        "total_hours": _hours(dto.get("sleepTimeSeconds")),
        "deep_min": _int((_num(dto.get("deepSleepSeconds")) or 0) / 60) or None,
        "light_min": _int((_num(dto.get("lightSleepSeconds")) or 0) / 60) or None,
        "rem_min": _int((_num(dto.get("remSleepSeconds")) or 0) / 60) or None,
        "awake_min": _int((_num(dto.get("awakeSleepSeconds")) or 0) / 60) or None,
        "score": _int(_get(dto, "sleepScores", "overall", "value")),
        "hrv_avg": _int(_get(hrv_raw or {}, "hrvSummary", "lastNightAvg")),
    }


def parse_training(readiness_raw, status_raw, max_raw) -> dict:
    rd = _first(readiness_raw) or {}
    status = status_raw or {}
    # training status / loads ficam em formatos que variam entre versões;
    # extração best-effort, raw_json preserva o payload completo.
    latest = _first(_get(status, "mostRecentTrainingStatus", "latestTrainingStatusData")) or {}
    if isinstance(_get(status, "mostRecentTrainingStatus", "latestTrainingStatusData"), dict):
        # latestTrainingStatusData é dict {deviceId: {...}}
        values = list(_get(status, "mostRecentTrainingStatus", "latestTrainingStatusData").values())
        latest = values[0] if values else {}
    vo2 = _get(_first(max_raw) or {}, "generic", "vo2MaxValue")
    return {
        "readiness_score": _int(rd.get("score")),
        "training_status": (latest.get("trainingStatus") or rd.get("level") or None),
        "vo2max": _num(vo2),
        "acute_load_7d": _num(latest.get("acuteTrainingLoad")),
        "chronic_load_28d": _num(latest.get("dailyTrainingLoadChronic")),
    }


def parse_workout(act: dict) -> tuple[str, dict]:
    activity_id = str(act.get("activityId") or "")
    dur = _num(act.get("duration"))
    dist = _num(act.get("distance"))
    return activity_id, {
        "start_at": act.get("startTimeLocal") or act.get("startTimeGMT"),
        "type": _get(act, "activityType", "typeKey"),
        "duration_min": round(dur / 60, 1) if dur else None,
        "distance_km": round(dist / 1000, 2) if dist else None,
        "avg_hr": _int(act.get("averageHR")),
        "max_hr": _int(act.get("maxHR")),
        "calories": _int(act.get("calories")),
        "training_effect_aerobic": _num(act.get("aerobicTrainingEffect")),
        "training_effect_anaerobic": _num(act.get("anaerobicTrainingEffect")),
    }


def parse_body_entries(raw: dict) -> list[tuple[str, dict]]:
    """get_body_composition retorna dict com dateWeightList (varia entre versões)."""
    entries = []
    rows = raw.get("dateWeightList") if isinstance(raw, dict) else None
    if not rows and isinstance(raw, dict):
        rows = raw.get("allMetrics", {}).get("metricsMap", {}) or []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ts = row.get("date") or row.get("calendarDate")
        if isinstance(ts, (int, float)):
            date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        elif isinstance(ts, str):
            date = ts[:10]
        else:
            continue
        weight_g = _num(row.get("weight"))
        entries.append((date, {
            "weight_kg": round(weight_g / 1000, 2) if weight_g else None,
            "body_fat_pct": _num(row.get("bodyFat")),
            "muscle_kg": (round(_num(row.get("muscleMass")) / 1000, 2)
                          if _num(row.get("muscleMass")) else None),
            "water_pct": _num(row.get("bodyWater")),
            "bmi": _num(row.get("bmi")),
        }))
    return entries


# ── sync ───────────────────────────────────────────────────────────────────────

def run_sync(repo: GarminRepository, client: GarminClient, scope: str, days: int = 3) -> dict:
    """Puxa dados das últimas `days` datas e grava no SQLite. Tolerante a falhas."""
    counts = {"daily": 0, "sleep": 0, "training": 0, "workouts": 0, "body": 0}
    if not client.authenticate():
        repo.log_sync(scope, ok=False, error="authentication failed")
        log.error("garmin sync (%s): authentication failed", scope)
        return counts

    last_error: Optional[str] = None

    for i in range(days):
        date = _date_offset(i)
        try:
            raw = client.get_daily_summary(date) or {}
            if raw:
                repo.upsert_daily(date, parse_daily(raw), json.dumps(raw, default=str))
                counts["daily"] += 1
        except Exception as exc:  # noqa: BLE001
            last_error = f"daily {date}: {exc}"
            log.warning("sync daily %s failed: %s", date, exc)

        try:
            sleep_raw = client.get_sleep(date) or {}
            hrv_raw = None
            try:
                hrv_raw = client.get_hrv(date) or {}
            except Exception:  # noqa: BLE001
                pass
            if sleep_raw:
                repo.upsert_sleep(date, parse_sleep(sleep_raw, hrv_raw), json.dumps(sleep_raw, default=str))
                counts["sleep"] += 1
        except Exception as exc:  # noqa: BLE001
            last_error = f"sleep {date}: {exc}"
            log.warning("sync sleep %s failed: %s", date, exc)

        try:
            rd = client.get_training_readiness(date)
            st = client.get_training_status(date)
            mx = client.get_max_metrics(date)
            fields = parse_training(rd, st, mx)
            if any(v is not None for v in fields.values()):
                repo.upsert_training(date, fields, json.dumps({"readiness": rd, "status": st, "max": mx}, default=str))
                counts["training"] += 1
        except Exception as exc:  # noqa: BLE001
            last_error = f"training {date}: {exc}"
            log.warning("sync training %s failed: %s", date, exc)

    try:
        for act in client.get_recent_activities(20):
            activity_id, fields = parse_workout(act)
            if activity_id:
                repo.upsert_workout(activity_id, fields, json.dumps(act, default=str))
                counts["workouts"] += 1
    except Exception as exc:  # noqa: BLE001
        last_error = f"workouts: {exc}"
        log.warning("sync workouts failed: %s", exc)

    try:
        body_raw = client.get_body_composition(_date_offset(30), _today()) or {}
        for date, fields in parse_body_entries(body_raw):
            if any(v is not None for v in fields.values()):
                repo.upsert_body(date, fields, "garmin", None)
                counts["body"] += 1
    except Exception as exc:  # noqa: BLE001
        last_error = f"body: {exc}"
        log.warning("sync body failed: %s", exc)

    ok = any(counts.values())
    repo.log_sync(scope, ok=ok, error=last_error)
    log.info("garmin sync (%s) done: %s", scope, counts)
    return counts


def add_manual_weight(repo: GarminRepository, weight_kg: float) -> None:
    repo.upsert_body(_today(), {"weight_kg": round(weight_kg, 2)}, "manual", None)


# ── formatters (lêem do SQLite, texto seco PT-BR) ──────────────────────────────

def format_today(repo: GarminRepository) -> str:
    sleep = repo.latest_sleep()
    training = repo.latest_training()
    daily = repo.latest_daily()
    workout = repo.latest_workout()
    lines = [f"Garmin — resumo de hoje ({_today()})"]
    if sleep:
        s = f"Sono ({sleep['date']}): {_hm(sleep['total_hours'])}"
        if sleep["score"] is not None:
            s += f", score {sleep['score']}"
        if sleep["hrv_avg"] is not None:
            s += f", HRV {sleep['hrv_avg']} ms"
        lines.append(s)
    if training:
        t = []
        if training["readiness_score"] is not None:
            t.append(f"readiness {training['readiness_score']}/100")
        if training["training_status"]:
            t.append(f"status {training['training_status']}")
        if t:
            lines.append("Treino: " + ", ".join(t))
    if daily:
        d = []
        if daily["body_battery_max"] is not None:
            d.append(f"body battery {daily['body_battery_min']}–{daily['body_battery_max']}")
        if daily["steps"] is not None:
            d.append(f"{daily['steps']} passos")
        if daily["calories_active"] is not None:
            d.append(f"{daily['calories_active']} kcal ativas")
        if d:
            lines.append(f"Dia ({daily['date']}): " + ", ".join(d))
    if workout:
        lines.append("Último treino: " + _workout_line(workout))
    if len(lines) == 1:
        lines.append("Sem dados sincronizados ainda. Use /garmin_sync.")
    return "\n".join(lines)


def format_sleep(repo: GarminRepository) -> str:
    s = repo.latest_sleep()
    if not s:
        return "Sem dados de sono. Use /garmin_sync."
    parts = [f"Sono da noite de {s['date']}: {_hm(s['total_hours'])}"]
    fases = []
    if s["deep_min"] is not None:
        fases.append(f"profundo {s['deep_min']}min")
    if s["light_min"] is not None:
        fases.append(f"leve {s['light_min']}min")
    if s["rem_min"] is not None:
        fases.append(f"REM {s['rem_min']}min")
    if s["awake_min"] is not None:
        fases.append(f"acordado {s['awake_min']}min")
    if fases:
        parts.append("Fases: " + ", ".join(fases))
    extra = []
    if s["score"] is not None:
        extra.append(f"score {s['score']}")
    if s["hrv_avg"] is not None:
        extra.append(f"HRV {s['hrv_avg']} ms")
    if extra:
        parts.append(", ".join(extra))
    return "\n".join(parts)


def format_hrv(repo: GarminRepository, days: int = 7) -> str:
    rows = [r for r in repo.list_sleep(days) if r["hrv_avg"] is not None]
    if not rows:
        return "Sem dados de HRV. Use /garmin_sync."
    rows = list(reversed(rows))  # ordem cronológica
    trend = " -> ".join(f"{r['date'][5:]}: {r['hrv_avg']}ms" for r in rows)
    vals = [r["hrv_avg"] for r in rows]
    avg = round(sum(vals) / len(vals))
    return f"HRV últimos {len(rows)} dias (média {avg} ms):\n{trend}"


def _workout_line(w) -> str:
    t = (w["type"] or "treino").replace("_", " ")
    parts = [t]
    if w["duration_min"] is not None:
        parts.append(f"{w['duration_min']:.0f}min")
    if w["distance_km"]:
        parts.append(f"{w['distance_km']:.2f}km")
    if w["avg_hr"] is not None:
        parts.append(f"FC média {w['avg_hr']}")
    if w["training_effect_aerobic"]:
        parts.append(f"TE aeróbico {w['training_effect_aerobic']:.1f}")
    when = (w["start_at"] or "")[:16].replace("T", " ")
    head = f"{when} " if when else ""
    return head + " · ".join(parts)


def format_workout(repo: GarminRepository, activity_id: Optional[str] = None) -> str:
    w = repo.get_workout(activity_id) if activity_id else repo.latest_workout()
    if not w:
        return "Treino não encontrado. Use /garmin_sync ou /garmin_treinos."
    lines = [f"Treino #{w['activity_id']}", _workout_line(w)]
    if w["calories"] is not None:
        lines.append(f"Calorias: {w['calories']}")
    if w["max_hr"] is not None:
        lines.append(f"FC máxima: {w['max_hr']}")
    if w["training_effect_anaerobic"]:
        lines.append(f"TE anaeróbico: {w['training_effect_anaerobic']:.1f}")
    return "\n".join(lines)


def format_workouts(repo: GarminRepository, n: int = 7) -> str:
    rows = repo.list_workouts(n)
    if not rows:
        return "Sem treinos registrados. Use /garmin_sync."
    lines = [f"Últimos {len(rows)} treinos:"]
    for w in rows:
        lines.append(f"#{w['activity_id']} · " + _workout_line(w))
    return "\n".join(lines)


def format_body(repo: GarminRepository) -> str:
    rows = repo.list_body(2)
    if not rows:
        return "Sem composição corporal. Use /garmin_sync ou /garmin_peso <valor>."
    cur = rows[0]
    parts = [f"Composição corporal ({cur['date']}, fonte {cur['source']}):"]
    if cur["weight_kg"] is not None:
        parts.append(f"Peso: {cur['weight_kg']} kg")
    if cur["body_fat_pct"] is not None:
        parts.append(f"Gordura: {cur['body_fat_pct']}%")
    if cur["muscle_kg"] is not None:
        parts.append(f"Músculo: {cur['muscle_kg']} kg")
    if cur["bmi"] is not None:
        parts.append(f"IMC: {cur['bmi']}")
    if len(rows) > 1 and cur["weight_kg"] is not None and rows[1]["weight_kg"] is not None:
        delta = round(cur["weight_kg"] - rows[1]["weight_kg"], 2)
        parts.append(f"Variação vs {rows[1]['date']}: {delta:+.2f} kg")
    return "\n".join(parts)


def format_status(repo: GarminRepository) -> str:
    t = repo.latest_training()
    if not t:
        return "Sem dados de training status. Use /garmin_sync."
    lines = [f"Training status ({t['date']}):"]
    if t["training_status"]:
        lines.append(f"Status: {t['training_status']}")
    if t["readiness_score"] is not None:
        lines.append(f"Readiness: {t['readiness_score']}/100")
    if t["vo2max"] is not None:
        lines.append(f"VO2max: {t['vo2max']}")
    if t["acute_load_7d"] is not None:
        lines.append(f"Carga aguda (7d): {t['acute_load_7d']}")
    if t["chronic_load_28d"] is not None:
        lines.append(f"Carga crônica (28d): {t['chronic_load_28d']}")
    return "\n".join(lines)


def format_week(repo: GarminRepository) -> str:
    return build_weekly_block(repo)


def format_sync_status(repo: GarminRepository) -> str:
    row = repo.last_sync()
    if not row:
        return "Nenhum sync registrado ainda."
    state = "ok" if row["ok"] else "falhou"
    msg = f"Último sync: {row['ran_at']} (escopo {row['scope']}, {state})"
    if row["error"]:
        msg += f"\nErro: {row['error'][:200]}"
    return msg


# ── report builders (jobs) ─────────────────────────────────────────────────────

def build_morning_report(repo: GarminRepository) -> str:
    sleep = repo.latest_sleep()
    training = repo.latest_training()
    daily = repo.latest_daily()
    lines = [f"Bom dia. Resumo Garmin ({_today()})."]
    if sleep:
        s = f"Dormiu {_hm(sleep['total_hours'])}"
        if sleep["score"] is not None:
            s += f" (score {sleep['score']}"
            s += f", HRV {sleep['hrv_avg']} ms)" if sleep["hrv_avg"] is not None else ")"
        lines.append(s + ".")
    if daily and daily["body_battery_max"] is not None:
        lines.append(f"Body battery: {daily['body_battery_min']}–{daily['body_battery_max']}%.")
    if training and training["readiness_score"] is not None:
        lines.append(f"Readiness: {training['readiness_score']}/100.")
    if len(lines) == 1:
        lines.append("Sem dados sincronizados — o relógio pode não ter sincronizado.")
    lines.append("Treino planejado para hoje?")
    return "\n".join(lines)


def build_evening_report(repo: GarminRepository) -> str:
    daily = repo.get_daily(_today()) or repo.latest_daily()
    lines = [f"Recap Garmin ({_today()})."]
    if daily:
        d = []
        if daily["steps"] is not None:
            d.append(f"{daily['steps']} passos")
        if daily["calories_active"] is not None:
            d.append(f"{daily['calories_active']} kcal ativas")
        if daily["stress_avg"] is not None:
            d.append(f"stress médio {daily['stress_avg']}")
        if daily["body_battery_min"] is not None:
            d.append(f"body battery mín {daily['body_battery_min']}%")
        if d:
            lines.append("Hoje: " + ", ".join(d) + ".")
    today_workouts = [w for w in repo.list_workouts(10) if (w["start_at"] or "")[:10] == _today()]
    if today_workouts:
        lines.append("Treino de hoje: " + "; ".join(_workout_line(w) for w in today_workouts) + ".")
    else:
        lines.append("Sem treino registrado hoje.")
    lines.append("Vai descansar bem?")
    return "\n".join(lines)


def build_weekly_block(repo: GarminRepository) -> str:
    sleep_rows = repo.list_sleep(7)
    sleep_vals = [r["total_hours"] for r in sleep_rows if r["total_hours"] is not None]
    hrv_vals = [r["hrv_avg"] for r in sleep_rows if r["hrv_avg"] is not None]
    workouts = repo.list_workouts(50)
    week_ago = _date_offset(7)
    week_workouts = [w for w in workouts if (w["start_at"] or "")[:10] >= week_ago]
    dist = sum(w["distance_km"] or 0 for w in week_workouts)
    cals = sum(w["calories"] or 0 for w in week_workouts)
    training_rows = repo.list_training(7)
    rd_vals = [r["readiness_score"] for r in training_rows if r["readiness_score"] is not None]
    body = repo.list_body(8)

    lines = ["Saúde — Garmin (últimos 7 dias):"]
    if sleep_vals:
        lines.append(f"Sono médio: {_hm(round(sum(sleep_vals) / len(sleep_vals), 2))}.")
    if hrv_vals:
        lines.append(f"HRV média: {round(sum(hrv_vals) / len(hrv_vals))} ms.")
    lines.append(f"Treinos: {len(week_workouts)}, {dist:.1f} km, {int(cals)} kcal.")
    if rd_vals:
        lines.append(f"Readiness média: {round(sum(rd_vals) / len(rd_vals))}/100.")
    if len(body) >= 2 and body[0]["weight_kg"] and body[-1]["weight_kg"]:
        delta = round(body[0]["weight_kg"] - body[-1]["weight_kg"], 2)
        lines.append(f"Peso: {body[0]['weight_kg']} kg ({delta:+.2f} kg na janela).")
    elif body and body[0]["weight_kg"]:
        lines.append(f"Peso: {body[0]['weight_kg']} kg.")
    if len(lines) == 1:
        lines.append("Sem dados na janela.")
    return "\n".join(lines)


# ── alertas reativos (porte de alerts.py, lendo do SQLite) ─────────────────────

def check_alerts(repo: GarminRepository) -> list[str]:
    """Retorna alertas disparados. Lista vazia = tudo normal (silêncio)."""
    alerts: list[str] = []

    # HRV em queda 3 noites seguidas (aproximação do alerts.py original;
    # baseline low não é persistido localmente — usa só a tendência estrita).
    sleep_rows = repo.list_sleep(3)
    hrv = [r["hrv_avg"] for r in sleep_rows if r["hrv_avg"] is not None]
    if len(hrv) == 3 and hrv[0] < hrv[1] < hrv[2]:
        trend = " -> ".join(f"{v}ms" for v in reversed(hrv))
        alerts.append(f"HRV em queda 3 noites seguidas: {trend}")

    # Sono < 6h em 2 noites seguidas.
    last2 = [r["total_hours"] for r in repo.list_sleep(2) if r["total_hours"] is not None]
    if len(last2) == 2 and all(h < 6 for h in last2):
        fmt = " · ".join(_hm(h) for h in reversed(last2))
        alerts.append(f"Sono curto 2 noites: {fmt} (< 6h cada)")

    # Body battery atual < 30 (lê o valor mais recente do raw_json do dia).
    daily = repo.latest_daily()
    if daily and daily["raw_json"]:
        try:
            recent = json.loads(daily["raw_json"]).get("bodyBatteryMostRecentValue")
        except (ValueError, TypeError):
            recent = daily["body_battery_min"]
        if recent is not None and recent < 30:
            alerts.append(f"Body battery em {recent} — recovery comprometida")

    return alerts
