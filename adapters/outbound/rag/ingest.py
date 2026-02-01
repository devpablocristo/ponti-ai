import uuid
from typing import Any

from pgvector.psycopg import register_vector

from adapters.outbound.db.session import DBSession
from adapters.outbound.rag.chunking import chunk_text
from adapters.outbound.rag.embeddings import embed_texts
from app.config import Settings


def ingest_documents(settings: Settings, project_id: str, documents: list[Any]) -> int:
    session = DBSession(settings)
    total_chunks = 0

    with session.connect() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            for doc in documents:
                doc_id = str(uuid.uuid4())
                metadata = doc.metadata if getattr(doc, "metadata", None) else {}
                cur.execute(
                    """
                    INSERT INTO ai_rag_documents (id, project_id, source, title, metadata, created_at)
                    VALUES (%(id)s, %(project_id)s, %(source)s, %(title)s, %(metadata)s, NOW())
                    """,
                    {
                        "id": doc_id,
                        "project_id": project_id,
                        "source": doc.source,
                        "title": doc.title,
                        "metadata": metadata,
                    },
                )

                chunks = chunk_text(doc.content)
                embeddings = embed_texts(chunks, settings.embedding_dim)

                for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                    chunk_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO ai_rag_chunks (id, document_id, project_id, chunk_index, content, created_at)
                        VALUES (%(id)s, %(document_id)s, %(project_id)s, %(chunk_index)s, %(content)s, NOW())
                        """,
                        {
                            "id": chunk_id,
                            "document_id": doc_id,
                            "project_id": project_id,
                            "chunk_index": idx,
                            "content": chunk,
                        },
                    )
                    cur.execute(
                        """
                        INSERT INTO ai_rag_embeddings (id, chunk_id, project_id, embedding, model, created_at)
                        VALUES (%(id)s, %(chunk_id)s, %(project_id)s, %(embedding)s, %(model)s, NOW())
                        """,
                        {
                            "id": str(uuid.uuid4()),
                            "chunk_id": chunk_id,
                            "project_id": project_id,
                            "embedding": embedding,
                            "model": settings.llm_provider,
                        },
                    )
                    total_chunks += 1

        conn.commit()

    return total_chunks
