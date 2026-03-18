-- phone-logger database schema

CREATE TABLE IF NOT EXISTS contacts (
    number TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    number_type TEXT DEFAULT 'private',  -- 'private', 'business', 'mobile'
    tags TEXT DEFAULT '[]',          -- JSON array
    notes TEXT,
    spam_score INTEGER,
    source TEXT NOT NULL DEFAULT 'sqlite',
    last_seen TEXT,                   -- ISO 8601 datetime
    created_at TEXT NOT NULL,         -- ISO 8601 datetime
    updated_at TEXT NOT NULL          -- ISO 8601 datetime
);

CREATE TABLE IF NOT EXISTS cache (
    number TEXT NOT NULL,
    adapter TEXT NOT NULL,
    result_json TEXT NOT NULL,        -- Full ResolveResult as JSON
    cached_at TEXT NOT NULL,          -- ISO 8601 datetime
    ttl_days INTEGER NOT NULL DEFAULT 7,
    PRIMARY KEY (number, adapter)
);

CREATE TABLE IF NOT EXISTS call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL,
    direction TEXT NOT NULL,          -- 'inbound', 'outbound'
    event_type TEXT NOT NULL,         -- 'ring', 'call', 'connect', 'disconnect'
    resolved_name TEXT,
    source TEXT,                      -- which adapter resolved it
    timestamp TEXT NOT NULL           -- ISO 8601 datetime
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_call_log_number ON call_log(number);
CREATE INDEX IF NOT EXISTS idx_call_log_timestamp ON call_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cache_adapter ON cache(adapter);
CREATE INDEX IF NOT EXISTS idx_cache_cached_at ON cache(cached_at);

-- Migrations: Add number_type column if it doesn't exist
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we use a workaround
CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY);

INSERT OR IGNORE INTO _migrations (name) VALUES ('add_number_type');
-- The actual column addition happens in Python code (Database._run_migrations)
