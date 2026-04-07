-- Conversaciones del asistente Ponti (por proyecto y usuario)

CREATE TABLE IF NOT EXISTS ai_conversations (
    id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'internal',
    title TEXT NOT NULL DEFAULT '',
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    tool_calls_count INT NOT NULL DEFAULT 0,
    tokens_input INT NOT NULL DEFAULT 0,
    tokens_output INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_conversations_project_user ON ai_conversations (project_id, user_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_project_updated ON ai_conversations (project_id, updated_at DESC);
