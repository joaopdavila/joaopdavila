-- 001_init.sql — schema bootstrap
-- Cria a tabela de auditoria de interações e nada mais.
-- A tabela schema_version é gerenciada pelo runner em app/database.py.

CREATE TABLE IF NOT EXISTS bot_interactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    direction       TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    command         TEXT,
    payload_preview TEXT,            -- truncado em 200 chars, sem PII sensível
    chat_id         TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_interactions_created
    ON bot_interactions (created_at);
