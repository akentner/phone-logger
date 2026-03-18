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

CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,              -- UUIDv7 for sortability
    connection_id INTEGER NOT NULL,   -- Fritz connection_id for call correlation
    caller_number TEXT NOT NULL,
    called_number TEXT NOT NULL,
    direction TEXT NOT NULL,          -- 'inbound', 'outbound'
    status TEXT NOT NULL,             -- 'ringing', 'dialing', 'answered', 'missed', 'notReached'
    device TEXT,                      -- Device name (DECT, VoIP, Fax, etc.), can be NULL
    device_type TEXT,                 -- Device type (dect, voip, fax, voicebox, etc.), can be NULL
    msn TEXT,                         -- MSN (internal phone number) involved
    trunk_id TEXT,                    -- Trunk ID (SIP0, ISDN0, etc.), can be NULL
    line_id INTEGER,                  -- Line ID (0-4) from PBX
    is_internal INTEGER DEFAULT 0,    -- 1 if both caller and called are internal MSNs
    started_at TEXT NOT NULL,         -- ISO 8601 datetime (RING or CALL event)
    connected_at TEXT,                -- ISO 8601 datetime (CONNECT event), NULL if not connected
    finished_at TEXT,                 -- ISO 8601 datetime (DISCONNECT event), NULL if still active
    duration_seconds INTEGER,         -- Duration in seconds, NULL if still active
    resolved_name TEXT,               -- Resolved name from resolver adapters
    created_at TEXT NOT NULL,         -- ISO 8601 datetime (record creation)
    updated_at TEXT NOT NULL          -- ISO 8601 datetime (last update)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_call_log_number ON call_log(number);
CREATE INDEX IF NOT EXISTS idx_call_log_timestamp ON call_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cache_adapter ON cache(adapter);
CREATE INDEX IF NOT EXISTS idx_cache_cached_at ON cache(cached_at);
CREATE INDEX IF NOT EXISTS idx_calls_connection_id ON calls(connection_id);
CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_direction ON calls(direction);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
CREATE INDEX IF NOT EXISTS idx_calls_line_id ON calls(line_id);

-- Migrations: Add number_type column if it doesn't exist
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we use a workaround
CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY);

INSERT OR IGNORE INTO _migrations (name) VALUES ('add_number_type');
-- The actual column addition happens in Python code (Database._run_migrations)
