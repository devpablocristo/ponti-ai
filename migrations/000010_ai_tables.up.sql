-- Tabla de auditoria de Ponti AI

CREATE TABLE IF NOT EXISTS ai_audit_logs (
    request_id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    intent TEXT NOT NULL,
    query_id TEXT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms INT NOT NULL,
    rows_count INT NOT NULL,
    status TEXT NOT NULL,
    error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_project_id ON ai_audit_logs (project_id);
