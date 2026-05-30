from __future__ import annotations

import sqlite3
from typing import Optional

from app.repositories.base import BaseRepository


class GarminRepository(BaseRepository):
    """SQL cru sobre as tabelas garmin_*. Upserts idempotentes por data/atividade."""

    # ── garmin_daily ────────────────────────────────────────────────────────

    def upsert_daily(self, date: str, fields: dict, raw_json: Optional[str]) -> None:
        self.execute(
            """
            INSERT INTO garmin_daily
                (date, steps, calories_total, calories_active, distance_km,
                 resting_hr, body_battery_max, body_battery_min, stress_avg, raw_json)
            VALUES (:date, :steps, :calories_total, :calories_active, :distance_km,
                    :resting_hr, :body_battery_max, :body_battery_min, :stress_avg, :raw_json)
            ON CONFLICT(date) DO UPDATE SET
                steps=excluded.steps,
                calories_total=excluded.calories_total,
                calories_active=excluded.calories_active,
                distance_km=excluded.distance_km,
                resting_hr=excluded.resting_hr,
                body_battery_max=excluded.body_battery_max,
                body_battery_min=excluded.body_battery_min,
                stress_avg=excluded.stress_avg,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            self._row_params(
                date, raw_json,
                ["steps", "calories_total", "calories_active", "distance_km",
                 "resting_hr", "body_battery_max", "body_battery_min", "stress_avg"],
                fields,
            ),
        )

    def get_daily(self, date: str) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM garmin_daily WHERE date = ?", (date,))

    def latest_daily(self) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM garmin_daily ORDER BY date DESC LIMIT 1")

    def list_daily(self, days: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM garmin_daily ORDER BY date DESC LIMIT ?", (days,)
        )

    # ── garmin_sleep ──────────────────────────────────────────────────────────

    def upsert_sleep(self, date: str, fields: dict, raw_json: Optional[str]) -> None:
        self.execute(
            """
            INSERT INTO garmin_sleep
                (date, total_hours, deep_min, light_min, rem_min, awake_min, score, hrv_avg, raw_json)
            VALUES (:date, :total_hours, :deep_min, :light_min, :rem_min, :awake_min, :score, :hrv_avg, :raw_json)
            ON CONFLICT(date) DO UPDATE SET
                total_hours=excluded.total_hours,
                deep_min=excluded.deep_min,
                light_min=excluded.light_min,
                rem_min=excluded.rem_min,
                awake_min=excluded.awake_min,
                score=excluded.score,
                hrv_avg=excluded.hrv_avg,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            self._row_params(
                date, raw_json,
                ["total_hours", "deep_min", "light_min", "rem_min", "awake_min",
                 "score", "hrv_avg"],
                fields,
            ),
        )

    def get_sleep(self, date: str) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM garmin_sleep WHERE date = ?", (date,))

    def latest_sleep(self) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM garmin_sleep ORDER BY date DESC LIMIT 1")

    def list_sleep(self, days: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM garmin_sleep ORDER BY date DESC LIMIT ?", (days,)
        )

    # ── garmin_training ───────────────────────────────────────────────────────

    def upsert_training(self, date: str, fields: dict, raw_json: Optional[str]) -> None:
        self.execute(
            """
            INSERT INTO garmin_training
                (date, readiness_score, training_status, vo2max, acute_load_7d, chronic_load_28d, raw_json)
            VALUES (:date, :readiness_score, :training_status, :vo2max, :acute_load_7d, :chronic_load_28d, :raw_json)
            ON CONFLICT(date) DO UPDATE SET
                readiness_score=excluded.readiness_score,
                training_status=excluded.training_status,
                vo2max=excluded.vo2max,
                acute_load_7d=excluded.acute_load_7d,
                chronic_load_28d=excluded.chronic_load_28d,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            self._row_params(
                date, raw_json,
                ["readiness_score", "training_status", "vo2max",
                 "acute_load_7d", "chronic_load_28d"],
                fields,
            ),
        )

    def get_training(self, date: str) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM garmin_training WHERE date = ?", (date,))

    def latest_training(self) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM garmin_training ORDER BY date DESC LIMIT 1")

    def list_training(self, days: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM garmin_training ORDER BY date DESC LIMIT ?", (days,)
        )

    # ── garmin_workouts ───────────────────────────────────────────────────────

    def upsert_workout(self, activity_id: str, fields: dict, raw_json: Optional[str]) -> None:
        params = {
            "activity_id": activity_id,
            "raw_json": raw_json,
            **{
                k: fields.get(k)
                for k in (
                    "start_at", "type", "duration_min", "distance_km", "avg_hr",
                    "max_hr", "calories", "training_effect_aerobic",
                    "training_effect_anaerobic",
                )
            },
        }
        self.execute(
            """
            INSERT INTO garmin_workouts
                (activity_id, start_at, type, duration_min, distance_km, avg_hr, max_hr,
                 calories, training_effect_aerobic, training_effect_anaerobic, raw_json)
            VALUES (:activity_id, :start_at, :type, :duration_min, :distance_km, :avg_hr, :max_hr,
                    :calories, :training_effect_aerobic, :training_effect_anaerobic, :raw_json)
            ON CONFLICT(activity_id) DO UPDATE SET
                start_at=excluded.start_at,
                type=excluded.type,
                duration_min=excluded.duration_min,
                distance_km=excluded.distance_km,
                avg_hr=excluded.avg_hr,
                max_hr=excluded.max_hr,
                calories=excluded.calories,
                training_effect_aerobic=excluded.training_effect_aerobic,
                training_effect_anaerobic=excluded.training_effect_anaerobic,
                raw_json=excluded.raw_json
            """,
            params,
        )

    def get_workout(self, activity_id: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM garmin_workouts WHERE activity_id = ?", (activity_id,)
        )

    def latest_workout(self) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM garmin_workouts ORDER BY start_at DESC LIMIT 1"
        )

    def list_workouts(self, n: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM garmin_workouts ORDER BY start_at DESC LIMIT ?", (n,)
        )

    # ── garmin_body_composition ───────────────────────────────────────────────

    def upsert_body(self, date: str, fields: dict, source: str, raw_json: Optional[str]) -> None:
        params = {
            "date": date,
            "source": source,
            "raw_json": raw_json,
            **{
                k: fields.get(k)
                for k in ("weight_kg", "body_fat_pct", "muscle_kg", "water_pct", "bmi")
            },
        }
        self.execute(
            """
            INSERT INTO garmin_body_composition
                (date, weight_kg, body_fat_pct, muscle_kg, water_pct, bmi, source, raw_json)
            VALUES (:date, :weight_kg, :body_fat_pct, :muscle_kg, :water_pct, :bmi, :source, :raw_json)
            ON CONFLICT(date) DO UPDATE SET
                weight_kg=excluded.weight_kg,
                body_fat_pct=excluded.body_fat_pct,
                muscle_kg=excluded.muscle_kg,
                water_pct=excluded.water_pct,
                bmi=excluded.bmi,
                source=excluded.source,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            params,
        )

    def latest_body(self) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM garmin_body_composition ORDER BY date DESC LIMIT 1"
        )

    def list_body(self, n: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM garmin_body_composition ORDER BY date DESC LIMIT ?", (n,)
        )

    # ── garmin_sync_log ───────────────────────────────────────────────────────

    def log_sync(self, scope: str, ok: bool, error: Optional[str] = None) -> None:
        self.execute(
            "INSERT INTO garmin_sync_log (scope, ok, error) VALUES (?, ?, ?)",
            (scope, 1 if ok else 0, error),
        )

    def last_sync(self) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM garmin_sync_log ORDER BY ran_at DESC LIMIT 1"
        )

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_params(date: str, raw_json: Optional[str], keys: list[str], fields: dict) -> dict:
        params = {"date": date, "raw_json": raw_json}
        for k in keys:
            params[k] = fields.get(k)
        return params
