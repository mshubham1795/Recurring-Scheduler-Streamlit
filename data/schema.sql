-- Recurring Scheduler SQLite Schema
-- Multi-user support with encrypted credential storage

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    last_login  TEXT
);

CREATE TABLE IF NOT EXISTS credentials (
    user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    encrypted_password  TEXT NOT NULL,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schedules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    study       TEXT NOT NULL,
    path        TEXT NOT NULL,
    file        TEXT NOT NULL,
    time        TEXT NOT NULL,
    freq        TEXT NOT NULL DEFAULT 'Weekly',
    days        TEXT DEFAULT '',
    end_date    TEXT DEFAULT '',
    priority    TEXT DEFAULT 'Medium',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(owner_id, path, file, time)
);

CREATE TABLE IF NOT EXISTS execution_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER REFERENCES schedules(id) ON DELETE SET NULL,
    owner_id    INTEGER NOT NULL REFERENCES users(id),
    study       TEXT,
    file_name   TEXT,
    status      TEXT NOT NULL,
    duration_sec REAL,
    message     TEXT,
    executed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_schedules_active ON schedules(active, owner_id);
CREATE INDEX IF NOT EXISTS idx_schedules_owner ON schedules(owner_id);
CREATE INDEX IF NOT EXISTS idx_exec_log_owner ON execution_log(owner_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_exec_log_schedule ON execution_log(schedule_id);
