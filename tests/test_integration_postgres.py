import os

import psycopg
import pytest
from pgvector.psycopg import register_vector

from app.config import Settings
from adapters.outbound.rag.ingest import ingest_documents
from adapters.outbound.rag.search import search_documents


@pytest.mark.integration
def test_rag_ingest_and_search() -> None:
    dsn = os.getenv("INTEGRATION_DB_DSN")
    if not dsn:
        pytest.skip("INTEGRATION_DB_DSN no configurado")

    settings = Settings(
        app_name="test",
        env="test",
        db_dsn=dsn,
        statement_timeout_ms=1000,
        max_limit=10,
        default_limit=5,
        embedding_dim=16,
        rag_top_k=2,
        llm_provider="stub",
        llm_model="stub",
        llm_api_key=None,
        llm_base_url=None,
        llm_timeout_s=5.0,
        llm_max_retries=1,
        insights_ratio_high=0.5,
        insights_ratio_medium=0.2,
        insights_spike_ratio=1.5,
        insights_cooldown_days=7,
        insights_impact_k=1.0,
        insights_impact_cap=2.0,
        insights_size_small_max=200,
        insights_size_medium_max=1000,
        insights_project_baseline_days=365,
        insights_min_samples_project=10,
        insights_baseline_lock_key=41001,
        insights_recompute_lock_key=41002,
        insights_baseline_batch_size=200,
        domain="agriculture",
        max_actions_allowed=4,
    )

    try:
        with psycopg.connect(dsn) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_rag_documents (
                        id UUID PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        title TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_rag_chunks (
                        id UUID PRIMARY KEY,
                        document_id UUID NOT NULL REFERENCES ai_rag_documents (id),
                        project_id TEXT NOT NULL,
                        chunk_index INT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_rag_embeddings (
                        id UUID PRIMARY KEY,
                        chunk_id UUID NOT NULL REFERENCES ai_rag_chunks (id),
                        project_id TEXT NOT NULL,
                        embedding VECTOR(16) NOT NULL,
                        model TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"No se pudo preparar DB para test de integracion: {exc}")

    class Doc:
        def __init__(self, source: str, title: str, content: str) -> None:
            self.source = source
            self.title = title
            self.content = content
            self.metadata = {}

    docs = [Doc("manual", "Guia", "Contenido de prueba")]
    ingested = ingest_documents(settings, "p-1", docs)
    assert ingested > 0

    result = search_documents(settings, "p-1", "prueba")
    assert result.top_k == 2
