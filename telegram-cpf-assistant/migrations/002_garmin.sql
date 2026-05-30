-- 002_garmin.sql — tabelas do domínio Garmin (Fase 1.5)
-- Cada tabela guarda raw_json TEXT com o payload bruto da API para
-- auditoria/replays sem re-chamar o Garmin.

-- Resumo diário: passos, calorias, distância, RHR, body battery, stress.
CREATE TABLE IF NOT EXISTS garmin_daily (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL UNIQUE,        -- YYYY-MM-DD
    steps             INTEGER,
    calories_total    INTEGER,
    calories_active   INTEGER,
    distance_km       REAL,
    resting_hr        INTEGER,
    body_battery_max  INTEGER,
    body_battery_min  INTEGER,
    stress_avg        INTEGER,
    raw_json          TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT
);

-- Sono por noite: duração, fases, score, HRV.
CREATE TABLE IF NOT EXISTS garmin_sleep (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,              -- YYYY-MM-DD da noite
    total_hours REAL,
    deep_min    INTEGER,
    light_min   INTEGER,
    rem_min     INTEGER,
    awake_min   INTEGER,
    score       INTEGER,
    hrv_avg     INTEGER,
    raw_json    TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT
);

-- Prontidão / status de treino por dia.
CREATE TABLE IF NOT EXISTS garmin_training (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT NOT NULL UNIQUE,         -- YYYY-MM-DD
    readiness_score  INTEGER,
    training_status  TEXT,
    vo2max           REAL,
    acute_load_7d    REAL,
    chronic_load_28d REAL,
    raw_json         TEXT,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at       TEXT
);

-- Treinos individuais (atividades).
CREATE TABLE IF NOT EXISTS garmin_workouts (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id              TEXT NOT NULL UNIQUE,
    start_at                 TEXT,                 -- ISO local
    type                     TEXT,
    duration_min             REAL,
    distance_km              REAL,
    avg_hr                   INTEGER,
    max_hr                   INTEGER,
    calories                 INTEGER,
    training_effect_aerobic  REAL,
    training_effect_anaerobic REAL,
    raw_json                 TEXT,
    created_at               TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Composição corporal por medição (Garmin, balança, InBody, manual).
CREATE TABLE IF NOT EXISTS garmin_body_composition (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL UNIQUE,            -- YYYY-MM-DD
    weight_kg    REAL,
    body_fat_pct REAL,
    muscle_kg    REAL,
    water_pct    REAL,
    bmi          REAL,
    source       TEXT,                            -- garmin/manual/relaxmedic/inbody/apple_health
    raw_json     TEXT,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT
);

-- Auditoria de cada execução de sync.
CREATE TABLE IF NOT EXISTS garmin_sync_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at TEXT DEFAULT CURRENT_TIMESTAMP,
    scope  TEXT,                                   -- ex: morning / weekly / manual
    ok     INTEGER NOT NULL DEFAULT 0,             -- 0/1
    error  TEXT
);

CREATE INDEX IF NOT EXISTS idx_garmin_workouts_start ON garmin_workouts (start_at);
