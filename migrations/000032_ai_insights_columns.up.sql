-- Agregar columnas faltantes para insights avanzados
BEGIN;

ALTER TABLE ai_insights
    ADD COLUMN IF NOT EXISTS impact_min DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS impact_max DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS impact_unit TEXT,
    ADD COLUMN IF NOT EXISTS confidence TEXT,
    ADD COLUMN IF NOT EXISTS dedupe_key TEXT,
    ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS computed_by TEXT,
    ADD COLUMN IF NOT EXISTS job_run_id TEXT,
    ADD COLUMN IF NOT EXISTS rules_version TEXT;

CREATE INDEX IF NOT EXISTS idx_ai_insights_dedupe
    ON ai_insights (project_id, entity_type, entity_id, dedupe_key);

COMMIT;
