-- 006_wedding.sql — domínio Casamento

CREATE TABLE IF NOT EXISTS wedding_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL
                CHECK (kind IN ('pendencia', 'pagamento', 'fornecedor', 'decisao')),
    description TEXT NOT NULL,
    vendor      TEXT,
    amount      REAL,
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'done', 'cancelled')),
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_wedding_kind_status ON wedding_items (kind, status);
