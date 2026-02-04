-- Persistencia de propuestas generadas por LLM para insights (v2)
BEGIN;

CREATE TABLE IF NOT EXISTS ai_insight_proposals (
    id UUID PRIMARY KEY,
    insight_id UUID NOT NULL REFERENCES ai_insights (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    proposal_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_version TEXT NOT NULL,
    tools_catalog_version TEXT NOT NULL,
    llm_provider TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_insight_proposals_insight_status_created
    ON ai_insight_proposals (insight_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_insight_proposals_project_created
    ON ai_insight_proposals (project_id, created_at DESC);

COMMIT;

