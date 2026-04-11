"""Repositorio unificado para tablas ai_* (conversaciones + dossier)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Json
from runtime.logging import get_logger

from src.config import Settings
from src.db.models import ConversationRow, DEFAULT_PROJECT_DOSSIER, ProjectDossierRow, deep_merge
from src.db.session import DBSession

logger = get_logger(__name__)


class AIRepository:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    # --- Conversaciones ---

    def create_conversation(self, *, project_id: str, user_id: str, title: str = "") -> ConversationRow:
        cid = str(uuid4())
        now = datetime.now(UTC)
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_conversations (
                        id, project_id, user_id, mode, title, messages,
                        tool_calls_count, tokens_input, tokens_output, created_at, updated_at
                    ) VALUES (
                        %(id)s, %(project_id)s, %(user_id)s, 'internal', %(title)s, '[]'::jsonb,
                        0, 0, 0, %(now)s, %(now)s
                    )
                    """,
                    {"id": cid, "project_id": project_id, "user_id": user_id, "title": title, "now": now},
                )
                conn.commit()
        return self.get_conversation(project_id, cid)  # type: ignore[return-value]

    def get_conversation(self, project_id: str, conversation_id: str) -> ConversationRow | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, project_id, user_id, mode, title, messages,
                           tool_calls_count, tokens_input, tokens_output, created_at, updated_at
                    FROM ai_conversations
                    WHERE id = %(id)s AND project_id = %(project_id)s
                    """,
                    {"id": conversation_id, "project_id": project_id},
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._to_conversation(row)

    def list_conversations(self, *, project_id: str, user_id: str, limit: int = 50) -> list[ConversationRow]:
        lim = max(1, min(int(limit), 200))
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, project_id, user_id, mode, title, messages,
                           tool_calls_count, tokens_input, tokens_output, created_at, updated_at
                    FROM ai_conversations
                    WHERE project_id = %(project_id)s AND user_id = %(user_id)s AND mode = 'internal'
                    ORDER BY updated_at DESC
                    LIMIT %(limit)s
                    """,
                    {"project_id": project_id, "user_id": user_id, "limit": lim},
                )
                rows = cur.fetchall()
        return [self._to_conversation(r) for r in rows]

    def append_messages(
        self,
        *,
        project_id: str,
        conversation_id: str,
        new_messages: list[dict[str, Any]],
        extra_tool_calls: int,
        tokens_input: int,
        tokens_output: int,
    ) -> ConversationRow | None:
        now = datetime.now(UTC)
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ai_conversations SET
                        messages = messages || %(new_messages)s::jsonb,
                        tool_calls_count = tool_calls_count + %(tc)s,
                        tokens_input = tokens_input + %(tin)s,
                        tokens_output = tokens_output + %(tout)s,
                        updated_at = %(now)s,
                        title = CASE
                            WHEN (title IS NULL OR title = '') AND %(first_user)s <> '' THEN LEFT(%(first_user)s, 200)
                            ELSE title
                        END
                    WHERE id = %(id)s AND project_id = %(project_id)s
                    RETURNING id
                    """,
                    {
                        "new_messages": Json(new_messages),
                        "tc": int(extra_tool_calls),
                        "tin": int(tokens_input),
                        "tout": int(tokens_output),
                        "now": now,
                        "first_user": next(
                            (str(m.get("content", "")) for m in new_messages if m.get("role") == "user"),
                            "",
                        ),
                        "id": conversation_id,
                        "project_id": project_id,
                    },
                )
                updated = cur.fetchone()
                conn.commit()
        if not updated:
            return None
        return self.get_conversation(project_id, conversation_id)

    def _to_conversation(self, row: dict[str, Any]) -> ConversationRow:
        raw_messages = row.get("messages") or []
        if isinstance(raw_messages, str):
            import json as _json
            try:
                raw_messages = _json.loads(raw_messages)
            except _json.JSONDecodeError:
                logger.warning("conversation_messages_invalid_json", conversation_id=str(row.get("id") or ""))
                raw_messages = []
        if not isinstance(raw_messages, list):
            raw_messages = []
        return ConversationRow(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            user_id=str(row["user_id"]),
            mode=str(row["mode"]),
            title=str(row.get("title") or ""),
            messages=list(raw_messages),
            tool_calls_count=int(row.get("tool_calls_count") or 0),
            tokens_input=int(row.get("tokens_input") or 0),
            tokens_output=int(row.get("tokens_output") or 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    # --- Dossier ---

    def get_or_create_dossier(self, project_id: str) -> ProjectDossierRow:
        row = self.get_dossier(project_id)
        if row is not None:
            return row
        now = datetime.now(UTC)
        dossier = copy.deepcopy(DEFAULT_PROJECT_DOSSIER)
        dossier["project"]["id"] = str(project_id)
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_project_dossiers (project_id, dossier, version, created_at, updated_at)
                    VALUES (%(project_id)s, %(dossier)s::jsonb, 1, %(now)s, %(now)s)
                    ON CONFLICT (project_id) DO NOTHING
                    """,
                    {"project_id": project_id, "dossier": Json(dossier), "now": now},
                )
                conn.commit()
        return self.get_dossier(project_id) or ProjectDossierRow(
            project_id=str(project_id),
            dossier=dossier,
            version=1,
            created_at=now,
            updated_at=now,
        )

    def get_dossier(self, project_id: str) -> ProjectDossierRow | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT project_id, dossier, version, created_at, updated_at
                    FROM ai_project_dossiers
                    WHERE project_id = %(project_id)s
                    """,
                    {"project_id": project_id},
                )
                row = cur.fetchone()
        if row is None:
            return None
        dossier = row.get("dossier") or {}
        if not isinstance(dossier, dict):
            dossier = copy.deepcopy(DEFAULT_PROJECT_DOSSIER)
        dossier = deep_merge(DEFAULT_PROJECT_DOSSIER, dossier)
        dossier["project"]["id"] = str(project_id)
        return ProjectDossierRow(
            project_id=str(row["project_id"]),
            dossier=dossier,
            version=int(row.get("version") or 1),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def save_dossier(self, project_id: str, dossier: dict[str, Any]) -> ProjectDossierRow:
        current = self.get_or_create_dossier(project_id)
        merged = deep_merge(current.dossier, dossier)
        merged["project"]["id"] = str(project_id)
        now = datetime.now(UTC)
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_project_dossiers (project_id, dossier, version, created_at, updated_at)
                    VALUES (%(project_id)s, %(dossier)s::jsonb, 1, %(now)s, %(now)s)
                    ON CONFLICT (project_id) DO UPDATE SET
                        dossier = EXCLUDED.dossier,
                        version = ai_project_dossiers.version + 1,
                        updated_at = EXCLUDED.updated_at
                    """,
                    {"project_id": project_id, "dossier": Json(merged), "now": now},
                )
                conn.commit()
        return self.get_or_create_dossier(project_id)
