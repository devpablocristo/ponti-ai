from pgvector.psycopg import register_vector

from adapters.outbound.db.session import DBSession
from adapters.outbound.rag.embeddings import embed_texts
from app.config import Settings
from domain.copilot.entities import RagSearchResult


def search_documents(settings: Settings, project_id: str, question: str) -> RagSearchResult:
    session = DBSession(settings)
    vector = embed_texts(settings, [question], settings.embedding_dim)[0]
    doc_ids: list[str] = []

    with session.connect() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id
                FROM ai_rag_embeddings e
                JOIN ai_rag_chunks c ON c.id = e.chunk_id
                JOIN ai_rag_documents d ON d.id = c.document_id
                WHERE e.project_id = %(project_id)s
                ORDER BY e.embedding <-> %(vector)s
                LIMIT %(limit)s
                """,
                {"project_id": project_id, "vector": vector, "limit": settings.rag_top_k},
            )
            rows = cur.fetchall()
            doc_ids = [row[0] for row in rows]

    answer = "Respuesta basada en documentos internos (MVP)."
    return RagSearchResult(doc_ids=doc_ids, top_k=settings.rag_top_k, answer=answer)
