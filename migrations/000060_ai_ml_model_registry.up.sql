CREATE TABLE IF NOT EXISTS ai_ml_models (
    model_type TEXT NOT NULL,
    version TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    trained_at TIMESTAMPTZ NOT NULL,
    n_samples_trained INT NOT NULL,
    hyperparameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    feature_names_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'trained',
    activated_at TIMESTAMPTZ NULL,
    deactivated_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (model_type, version)
);

CREATE INDEX IF NOT EXISTS idx_ai_ml_models_type_created
    ON ai_ml_models (model_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_ml_models_active
    ON ai_ml_models (model_type, is_active)
    WHERE is_active = TRUE;
