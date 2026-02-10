CREATE TABLE IF NOT EXISTS ai_recompute_queue (
    project_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    reason TEXT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_run_at TIMESTAMPTZ NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    last_error TEXT NULL,
    locked_by TEXT NULL,
    locked_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_recompute_queue_status_next_run
ON ai_recompute_queue (status, next_run_at);

CREATE INDEX IF NOT EXISTS idx_ai_recompute_queue_locked_at
ON ai_recompute_queue (locked_at);
