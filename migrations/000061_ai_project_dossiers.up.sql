-- Dossier persistente por proyecto para el asesor de Ponti

CREATE TABLE IF NOT EXISTS ai_project_dossiers (
    project_id TEXT PRIMARY KEY,
    dossier JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_project_dossiers_updated
    ON ai_project_dossiers (updated_at DESC);
