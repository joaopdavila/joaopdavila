-- 005_health_closings.sql — check-in matinal e fechamento diário

CREATE TABLE IF NOT EXISTS health_checkins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    checkin_date  TEXT NOT NULL UNIQUE,        -- YYYY-MM-DD (1 por dia, upsert)
    weight_kg     REAL,
    workout       TEXT,
    sleep_hours   REAL,
    sleep_note    TEXT,
    priority      TEXT,
    raw_response  TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_closings (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    closing_date         TEXT NOT NULL UNIQUE,
    main_task_done       INTEGER,
    had_relevant_expense INTEGER,
    health_done          INTEGER,
    tomorrow_pending     TEXT,
    raw_response         TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
