#!/usr/bin/env python3
from __future__ import annotations

"""
Importa dados históricos de composição corporal do garmin-dashboard para a
tabela garmin_body_composition do cpf-assistant. Execução única (one-shot).

Fontes (do checkout do garmin-dashboard):
  - inbody_data.csv        (date,weight_kg,fat_pct,muscle_kg,fat_kg,source)
  - relaxmedic_data.csv    (date,time,weight_kg,fat_pct,muscle_kg,bone_kg,
                            hydration_pct,visceral_fat_rating,metabolic_age,bmi)
  - apple_health_weight.json (registros Apple Health: peso + gordura%)

Deduplicação por data, prioridade: relaxmedic > inbody > apple_health
(mais campos = maior prioridade). Tolerante a falhas: linhas com erro vão para
data/garmin_import_errors.log e não abortam o import.

Uso:
  python migrations/scripts/import_garmin_legacy.py \
      --source-dir ../garmin-dashboard [--dry-run]
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402
from app.database import run_migrations  # noqa: E402
from app.repositories.garmin_repo import GarminRepository  # noqa: E402

ERROR_LOG = PROJECT_ROOT / "data" / "garmin_import_errors.log"

# prioridade: maior número vence na deduplicação por data
PRIORITY = {"relaxmedic": 3, "inbody": 2, "apple_health": 1}

log = logging.getLogger("import_garmin_legacy")


def _err(msg: str) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")
    log.warning(msg)


def _f(v) -> float | None:
    try:
        v = (v or "").strip() if isinstance(v, str) else v
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def load_inbody(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        log.info("inbody csv ausente: %s", path)
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            try:
                date = (row.get("date") or "").strip()
                if not date:
                    continue
                out.append({
                    "date": date,
                    "source": "inbody",
                    "fields": {
                        "weight_kg": _f(row.get("weight_kg")),
                        "body_fat_pct": _f(row.get("fat_pct")),
                        "muscle_kg": _f(row.get("muscle_kg")),
                        "water_pct": None,
                        "bmi": None,
                    },
                    "raw": row,
                })
            except Exception as exc:  # noqa: BLE001
                _err(f"inbody linha {i}: {exc}")
    return out


def load_relaxmedic(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        log.info("relaxmedic csv ausente: %s", path)
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            try:
                date = (row.get("date") or "").strip()
                if not date:
                    continue
                out.append({
                    "date": date,
                    "source": "relaxmedic",
                    "fields": {
                        "weight_kg": _f(row.get("weight_kg")),
                        "body_fat_pct": _f(row.get("fat_pct")),
                        "muscle_kg": _f(row.get("muscle_kg")),
                        "water_pct": _f(row.get("hydration_pct")),
                        "bmi": _f(row.get("bmi")),
                    },
                    "raw": row,
                })
            except Exception as exc:  # noqa: BLE001
                _err(f"relaxmedic linha {i}: {exc}")
    return out


def load_apple_health(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        log.info("apple health json ausente: %s", path)
        return out
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _err(f"apple_health json inválido: {exc}")
        return out

    weights: dict[str, float] = {}
    fats: dict[str, float] = {}
    for r in records:
        try:
            date = (r.get("startDate") or "")[:10]
            rtype = r.get("type", "")
            if "BodyMass" in rtype and "Index" not in rtype:
                val = _f(r.get("value"))
                if val is None:
                    continue
                if r.get("unit") == "lb":
                    val *= 0.453592
                weights.setdefault(date, round(val, 2))
            elif "FatPercentage" in rtype:
                val = _f(r.get("value"))
                if val is None:
                    continue
                if val <= 1.0:
                    val *= 100
                fats[date] = round(val, 1)
        except Exception as exc:  # noqa: BLE001
            _err(f"apple_health registro: {exc}")

    for date, w in weights.items():
        out.append({
            "date": date,
            "source": "apple_health",
            "fields": {
                "weight_kg": w,
                "body_fat_pct": fats.get(date),
                "muscle_kg": None,
                "water_pct": None,
                "bmi": None,
            },
            "raw": {"weight_kg": w, "fat_pct": fats.get(date)},
        })
    return out


def dedup(entries: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for e in entries:
        if e["fields"].get("weight_kg") is None:
            continue
        date = e["date"]
        if date not in best or PRIORITY[e["source"]] > PRIORITY[best[date]["source"]]:
            best[date] = e
    return [best[d] for d in sorted(best)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        default=str((PROJECT_ROOT.parent / "garmin-dashboard")),
        help="diretório do checkout do garmin-dashboard",
    )
    parser.add_argument("--dry-run", action="store_true", help="não grava, só mostra")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    src = Path(args.source_dir).resolve()

    entries = (
        load_inbody(src / "inbody_data.csv")
        + load_relaxmedic(src / "relaxmedic_data.csv")
        + load_apple_health(src / "apple_health_weight.json")
    )
    merged = dedup(entries)
    log.info(
        "carregados %d registros, %d após dedup por data", len(entries), len(merged)
    )

    if args.dry_run:
        for e in merged:
            log.info("[DRY] %s %s %s", e["date"], e["source"], e["fields"])
        return 0

    settings = Settings.load()
    run_migrations(settings.database_path)
    repo = GarminRepository(settings.database_path)
    ok = err = 0
    try:
        for e in merged:
            try:
                repo.upsert_body(
                    e["date"], e["fields"], e["source"],
                    json.dumps(e["raw"], default=str),
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001
                _err(f"upsert {e['date']} ({e['source']}): {exc}")
                err += 1
    finally:
        repo.close()

    log.info("import concluído: %d ok, %d erros", ok, err)
    if err:
        log.info("erros registrados em %s", ERROR_LOG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
