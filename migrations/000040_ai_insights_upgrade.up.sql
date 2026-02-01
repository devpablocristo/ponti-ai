-- Extender ai_insights con impacto, dedupe y metadatos de job
BEGIN;

ALTER TABLE ai_insights
    ADD COLUMN IF NOT EXISTS impact_min DOUBLE PRECISION NULL,
    ADD COLUMN IF NOT EXISTS impact_max DOUBLE PRECISION NULL,
    ADD COLUMN IF NOT EXISTS impact_unit TEXT NULL,
    ADD COLUMN IF NOT EXISTS confidence TEXT NULL,
    ADD COLUMN IF NOT EXISTS dedupe_key TEXT NULL,
    ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS computed_by TEXT NOT NULL DEFAULT 'on_demand',
    ADD COLUMN IF NOT EXISTS job_run_id UUID NULL,
    ADD COLUMN IF NOT EXISTS rules_version TEXT NOT NULL DEFAULT 'v1';

CREATE INDEX IF NOT EXISTS idx_ai_insights_dedupe
    ON ai_insights (project_id, entity_type, entity_id, dedupe_key);

COMMIT;
