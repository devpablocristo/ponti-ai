-- Revertir baselines de insights
BEGIN;

DROP INDEX IF EXISTS idx_ai_baselines_scope_feature_window;
DROP TABLE IF EXISTS ai_baselines;

COMMIT;
