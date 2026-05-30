from __future__ import annotations

import sqlite3

from app.repositories.base import BaseRepository


class HealthRepository(BaseRepository):
    # ── check-ins ────────────────────────────────────────────────────────────

    def upsert_checkin(self, checkin_date: str, fields: dict) -> None:
        self.execute(
            """
            INSERT INTO health_checkins
                (checkin_date, weight_kg, workout, sleep_hours, sleep_note, priority, raw_response)
            VALUES (:checkin_date, :weight_kg, :workout, :sleep_hours, :sleep_note, :priority, :raw_response)
            ON CONFLICT(checkin_date) DO UPDATE SET
                weight_kg=COALESCE(excluded.weight_kg, weight_kg),
                workout=COALESCE(excluded.workout, workout),
                sleep_hours=COALESCE(excluded.sleep_hours, sleep_hours),
                sleep_note=COALESCE(excluded.sleep_note, sleep_note),
                priority=COALESCE(excluded.priority, priority),
                raw_response=COALESCE(excluded.raw_response, raw_response)
            """,
            {
                "checkin_date": checkin_date,
                "weight_kg": fields.get("weight_kg"),
                "workout": fields.get("workout"),
                "sleep_hours": fields.get("sleep_hours"),
                "sleep_note": fields.get("sleep_note"),
                "priority": fields.get("priority"),
                "raw_response": fields.get("raw_response"),
            },
        )

    def get_checkin(self, checkin_date: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM health_checkins WHERE checkin_date = ?", (checkin_date,)
        )

    def checkins_between(self, start: str, end: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM health_checkins WHERE checkin_date BETWEEN ? AND ? "
            "ORDER BY checkin_date ASC",
            (start, end),
        )

    # ── fechamentos ──────────────────────────────────────────────────────────

    def upsert_closing(self, closing_date: str, fields: dict) -> None:
        self.execute(
            """
            INSERT INTO daily_closings
                (closing_date, main_task_done, had_relevant_expense, health_done,
                 tomorrow_pending, raw_response)
            VALUES (:closing_date, :main_task_done, :had_relevant_expense, :health_done,
                    :tomorrow_pending, :raw_response)
            ON CONFLICT(closing_date) DO UPDATE SET
                main_task_done=COALESCE(excluded.main_task_done, main_task_done),
                had_relevant_expense=COALESCE(excluded.had_relevant_expense, had_relevant_expense),
                health_done=COALESCE(excluded.health_done, health_done),
                tomorrow_pending=COALESCE(excluded.tomorrow_pending, tomorrow_pending),
                raw_response=COALESCE(excluded.raw_response, raw_response)
            """,
            {
                "closing_date": closing_date,
                "main_task_done": fields.get("main_task_done"),
                "had_relevant_expense": fields.get("had_relevant_expense"),
                "health_done": fields.get("health_done"),
                "tomorrow_pending": fields.get("tomorrow_pending"),
                "raw_response": fields.get("raw_response"),
            },
        )

    def get_closing(self, closing_date: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM daily_closings WHERE closing_date = ?", (closing_date,)
        )
