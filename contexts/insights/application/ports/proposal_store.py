from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol


ProposalStatus = Literal["ok", "error"]


@dataclass(frozen=True)
class StoredProposal:
    id: str
    insight_id: str
    project_id: str
    proposal: dict[str, Any]
    prompt_version: str
    tools_catalog_version: str
    llm_provider: str
    llm_model: str
    status: ProposalStatus
    error_message: str | None
    created_at: datetime


class ProposalStorePort(Protocol):
    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        ...

    def get_latest(self, insight_id: str) -> StoredProposal | None:
        ...

    def insert(
        self,
        *,
        insight_id: str,
        project_id: str,
        proposal: dict[str, Any],
        prompt_version: str,
        tools_catalog_version: str,
        llm_provider: str,
        llm_model: str,
        status: ProposalStatus,
        error_message: str | None,
    ) -> str:
        ...

