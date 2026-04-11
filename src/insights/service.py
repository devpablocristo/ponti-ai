"""Use cases de insights: compute, get, summary, record_action."""

from __future__ import annotations

import time
import uuid
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from src.insights.domain import (
    AuditRecord,
    ComputeInsightsResult,
    Insight,
    InsightSummary,
    RecordActionResult,
)

HANDLED_COMPUTE_ERRORS = (ValueError, RuntimeError, KeyError, OSError)
HANDLED_PROPOSAL_ERRORS = (ValueError, RuntimeError, KeyError, OSError)
HANDLED_RECORD_ACTION_ERRORS = (ValueError, RuntimeError, KeyError, OSError)


class ComputeInsights:
    def __init__(
        self,
        feature_repo,
        model_runner,
        insight_repo,
        audit_logger,
        proposal_store,
        insight_planner,
        insight_history,
        domain: str,
        max_actions_allowed: int,
        llm_provider: str,
        llm_model: str,
        insight_chat_enabled: bool = True,
    ) -> None:
        self.feature_repo = feature_repo
        self.model_runner = model_runner
        self.insight_repo = insight_repo
        self.audit_logger = audit_logger
        self.proposal_store = proposal_store
        self.insight_planner = insight_planner
        self.insight_history = insight_history
        self.domain = domain
        self.max_actions_allowed = max_actions_allowed
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.insight_chat_enabled = insight_chat_enabled

    def handle(
        self,
        project_id: str,
        user_id: str,
        computed_by: str = "on_demand",
        job_run_id: str | None = None,
        max_features: int | None = None,
    ) -> ComputeInsightsResult:
        request_id = str(uuid.uuid4())
        started = time.time()
        status = "ok"
        error = None
        computed = 0
        created = 0
        rules_created = 0
        filtered: list[Insight] = []

        try:
            features = self.feature_repo.fetch_features(project_id)
            if max_features is not None:
                features = features[: max(0, int(max_features))]
            computed = len(features)
            insights = self.model_runner.compute(project_id, features)
            now = datetime.now(timezone.utc)
            for insight in insights:
                if insight.dedupe_key:
                    existing = self.insight_repo.get_active_by_dedupe(
                        project_id=project_id,
                        entity_type=insight.entity_type,
                        entity_id=insight.entity_id,
                        dedupe_key=insight.dedupe_key,
                    )
                    if existing and existing.cooldown_until and existing.cooldown_until > now:
                        continue
                filtered.append(replace(insight, computed_by=computed_by, job_run_id=job_run_id))
            created = self.insight_repo.upsert_many(filtered)
            rules_created = created

            if self.insight_chat_enabled:
                request_scope = self._planner_request_scope()
                with request_scope:
                    for insight in filtered:
                        self._maybe_generate_proposal(project_id=project_id, insight=insight)
        except HANDLED_COMPUTE_ERRORS as exc:
            status = "error"
            error = str(exc)

        duration_ms = int((time.time() - started) * 1000)
        self.audit_logger.log(
            AuditRecord(
                request_id=request_id,
                user_id=user_id,
                project_id=project_id,
                question="insights_compute",
                intent="insights",
                query_id="compute",
                params={"project_id": project_id, "rules_insights_created": rules_created, "max_features": max_features},
                duration_ms=duration_ms,
                rows_count=created,
                status=status,
                error=error,
            )
        )

        return ComputeInsightsResult(
            request_id=request_id,
            computed=computed,
            insights_created=created,
            rules_insights_created=rules_created,
            projected_insights=filtered if status == "ok" else [],
        )

    def _planner_request_scope(self):
        request_scope = getattr(self.insight_planner, "request_scope", None)
        if callable(request_scope):
            return request_scope()
        return nullcontext()

    def _maybe_generate_proposal(self, *, project_id: str, insight: Insight) -> None:
        if insight.status != "new":
            return
        if int(insight.severity) < 70:
            return
        evidence = insight.evidence if isinstance(insight.evidence, dict) else {}
        n_samples = int(evidence.get("n_samples", 0) or 0)
        if n_samples < 30:
            return
        if self.proposal_store.get_latest_ok(insight.id) is not None:
            return

        history = self.insight_history.get_history(project_id, insight.entity_type, insight.entity_id, limit=6)
        previous = [
            {"id": item.id, "type": item.type, "severity": item.severity, "status": item.status, "computed_at": item.computed_at.isoformat(), "title": item.title}
            for item in history if item.id != insight.id
        ][:5]
        actions = self.insight_history.get_recent_actions(project_id, limit=5)
        previous_actions = [{"insight_id": a.insight_id, "user_id": a.user_id, "action": a.action, "created_at": a.created_at.isoformat()} for a in actions]
        historical_context = {"previous_insights": previous, "previous_actions": previous_actions, "outcomes": {}}

        prompt_version = getattr(self.insight_planner, "prompt_version", "unknown")
        tools_catalog_version = getattr(self.insight_planner, "tools_catalog_version", "unknown")

        try:
            proposal = self.insight_planner.plan(insight=insight, historical_context=historical_context, domain=self.domain, max_actions_allowed=self.max_actions_allowed)
            self.proposal_store.insert(
                insight_id=insight.id, project_id=project_id, proposal=proposal,
                prompt_version=str(prompt_version), tools_catalog_version=str(tools_catalog_version),
                llm_provider=self.llm_provider or "unknown", llm_model=self.llm_model or "unknown",
                status="ok", error_message=None,
            )
        except HANDLED_PROPOSAL_ERRORS as exc:
            self.proposal_store.insert(
                insight_id=insight.id, project_id=project_id, proposal={},
                prompt_version=str(prompt_version), tools_catalog_version=str(tools_catalog_version),
                llm_provider=self.llm_provider or "unknown", llm_model=self.llm_model or "unknown",
                status="error", error_message=str(exc),
            )


class GetInsights:
    def __init__(self, insight_repo) -> None:
        self.insight_repo = insight_repo

    def handle(self, project_id: str, entity_type: str, entity_id: str) -> list[Insight]:
        return self.insight_repo.get_by_entity(project_id, entity_type, entity_id)


class GetSummary:
    def __init__(self, insight_repo) -> None:
        self.insight_repo = insight_repo

    def handle(self, project_id: str) -> InsightSummary:
        return self.insight_repo.get_summary(project_id)


class RecordAction:
    def __init__(self, insight_repo, audit_logger) -> None:
        self.insight_repo = insight_repo
        self.audit_logger = audit_logger

    def handle(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> RecordActionResult:
        request_id = str(uuid.uuid4())
        started = time.time()
        status = "ok"
        error = None

        try:
            self.insight_repo.record_action(insight_id, project_id, user_id, action, new_status)
        except HANDLED_RECORD_ACTION_ERRORS as exc:
            status = "error"
            error = str(exc)

        duration_ms = int((time.time() - started) * 1000)
        self.audit_logger.log(
            AuditRecord(
                request_id=request_id,
                user_id=user_id,
                project_id=project_id,
                question=f"record_action:{action}",
                intent="action",
                query_id="record_action",
                params={"insight_id": insight_id, "action": action, "new_status": new_status},
                duration_ms=duration_ms,
                rows_count=1 if status == "ok" else 0,
                status=status,
                error=error,
            )
        )

        return RecordActionResult(request_id=request_id)
