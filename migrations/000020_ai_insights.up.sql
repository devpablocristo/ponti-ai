-- Tablas de insights y acciones
CREATE TABLE IF NOT EXISTS ai_insights (
    id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    type TEXT NOT NULL,
    severity INT NOT NULL,
    priority INT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanations_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL,
    features_version TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_insight_actions (
    id UUID PRIMARY KEY,
    insight_id UUID NOT NULL REFERENCES ai_insights (id),
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_entity_scores (
    id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    score FLOAT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_insights_project_status_valid
    ON ai_insights (project_id, status, valid_until);

CREATE INDEX IF NOT EXISTS idx_ai_insights_entity_computed
    ON ai_insights (project_id, entity_type, entity_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_insight_actions_project
    ON ai_insight_actions (project_id);
