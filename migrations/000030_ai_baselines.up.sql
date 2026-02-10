-- Tablas de baselines para insights
BEGIN;

CREATE TABLE IF NOT EXISTS ai_baselines (
    id UUID PRIMARY KEY,
    scope_type TEXT NOT NULL DEFAULT 'global',
    scope_id TEXT NULL,
    cohort_key TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    window_name TEXT NOT NULL,
    p50 DOUBLE PRECISION NOT NULL,
    p75 DOUBLE PRECISION NOT NULL,
    p90 DOUBLE PRECISION NOT NULL,
    n_samples INT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_baselines_scope_feature_window
    ON ai_baselines (scope_type, scope_id, cohort_key, feature_name, window_name);

COMMIT;
