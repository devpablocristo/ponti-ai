import json
import uuid

from adapters.outbound.db.session import DBSession
from app.config import Settings
from contexts.insights.application.ports.proposal_store import ProposalStatus, ProposalStorePort, StoredProposal


def _row_to_proposal(row: dict) -> StoredProposal:
    return StoredProposal(
        id=str(row["id"]),
        insight_id=str(row["insight_id"]),
        project_id=str(row["project_id"]),
        proposal=row.get("proposal_json", {}) or {},
        prompt_version=str(row["prompt_version"]),
        tools_catalog_version=str(row.get("tools_catalog_version", "")),
        llm_provider=str(row.get("llm_provider", "")),
        llm_model=str(row.get("llm_model", "")),
        status=row.get("status", "error"),
        error_message=row.get("error_message"),
        created_at=row["created_at"],
    )


class ProposalStorePG(ProposalStorePort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insight_proposals
                    WHERE insight_id = %(insight_id)s::uuid
                      AND status = 'ok'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    {"insight_id": insight_id},
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_proposal(dict(row))

    def get_latest(self, insight_id: str) -> StoredProposal | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insight_proposals
                    WHERE insight_id = %(insight_id)s::uuid
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    {"insight_id": insight_id},
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_proposal(dict(row))

    def insert(
        self,
        *,
        insight_id: str,
        project_id: str,
        proposal: dict,
        prompt_version: str,
        tools_catalog_version: str,
        llm_provider: str,
        llm_model: str,
        status: ProposalStatus,
        error_message: str | None,
    ) -> str:
        proposal_id = str(uuid.uuid4())
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_insight_proposals (
                        id, insight_id, project_id, proposal_json,
                        prompt_version, tools_catalog_version, llm_provider, llm_model,
                        status, error_message, created_at
                    ) VALUES (
                        %(id)s, %(insight_id)s, %(project_id)s, %(proposal_json)s,
                        %(prompt_version)s, %(tools_catalog_version)s, %(llm_provider)s, %(llm_model)s,
                        %(status)s, %(error_message)s, NOW()
                    )
                    """,
                    {
                        "id": proposal_id,
                        "insight_id": insight_id,
                        "project_id": project_id,
                        "proposal_json": json.dumps(proposal),
                        "prompt_version": prompt_version,
                        "tools_catalog_version": tools_catalog_version,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "status": status,
                        "error_message": error_message,
                    },
                )
            conn.commit()
        return proposal_id

