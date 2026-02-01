-- Revertir extension de ai_insights
BEGIN;

DROP INDEX IF EXISTS idx_ai_insights_dedupe;

ALTER TABLE ai_insights
    DROP COLUMN IF EXISTS impact_min,
    DROP COLUMN IF EXISTS impact_max,
    DROP COLUMN IF EXISTS impact_unit,
    DROP COLUMN IF EXISTS confidence,
    DROP COLUMN IF EXISTS dedupe_key,
    DROP COLUMN IF EXISTS cooldown_until,
    DROP COLUMN IF EXISTS computed_by,
    DROP COLUMN IF EXISTS job_run_id,
    DROP COLUMN IF EXISTS rules_version;

COMMIT;
