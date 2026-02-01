-- Tablas de RAG y auditoria del AI Copilot Service
CREATE TABLE IF NOT EXISTS ai_rag_documents (
    id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_rag_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES ai_rag_documents (id),
    project_id TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_rag_embeddings (
    id UUID PRIMARY KEY,
    chunk_id UUID NOT NULL REFERENCES ai_rag_chunks (id),
    project_id TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_audit_logs (
    request_id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    intent TEXT NOT NULL,
    query_id TEXT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms INT NOT NULL,
    rows_count INT NOT NULL,
    status TEXT NOT NULL,
    error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_rag_documents_project_id ON ai_rag_documents (project_id);
CREATE INDEX IF NOT EXISTS idx_ai_rag_chunks_project_id ON ai_rag_chunks (project_id);
CREATE INDEX IF NOT EXISTS idx_ai_rag_embeddings_project_id ON ai_rag_embeddings (project_id);
CREATE INDEX IF NOT EXISTS idx_ai_audit_logs_project_id ON ai_audit_logs (project_id);
