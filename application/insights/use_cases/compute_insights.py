import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from application.insights.dto import ComputeInsightsResult
from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from application.insights.ports.feature_repository import FeatureRepositoryPort
from application.insights.ports.insight_history import InsightHistoryPort
from application.insights.ports.ml_detector import MLDetectorPort
from application.insights.ports.metrics import MetricsPort
from application.insights.ports.insight_repository import InsightRepositoryPort
from application.insights.ports.insight_planner import InsightPlannerPort
from application.insights.ports.model_runner import ModelRunnerPort
from application.insights.ports.proposal_store import ProposalStorePort

HANDLED_COMPUTE_ERRORS = (ValueError, RuntimeError, KeyError, OSError)
HANDLED_ML_DETECT_ERRORS = (ValueError, RuntimeError, KeyError, OSError)
HANDLED_PROPOSAL_ERRORS = (ValueError, RuntimeError, KeyError, OSError)


class ComputeInsights:
    def __init__(
        self,
        feature_repo: FeatureRepositoryPort,
        model_runner: ModelRunnerPort,
        insight_repo: InsightRepositoryPort,
        audit_logger: AuditLoggerPort,
        proposal_store: ProposalStorePort,
        insight_planner: InsightPlannerPort,
        insight_history: InsightHistoryPort,
        domain: str,
        max_actions_allowed: int,
        llm_provider: str,
        llm_model: str,
        ml_detector: MLDetectorPort | None = None,
        ml_shadow_mode: bool = False,
        metrics: MetricsPort | None = None,
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
        self.ml_detector = ml_detector
        self.ml_shadow_mode = ml_shadow_mode
        self.metrics = metrics

    def handle(
        self,
        project_id: str,
        user_id: str,
        computed_by: str = "on_demand",
        job_run_id: str | None = None,
    ) -> ComputeInsightsResult:
        request_id = str(uuid.uuid4())
        started = time.time()
        status = "ok"
        error = None
        computed = 0
        created = 0
        rules_created = 0
        ml_created = 0

        try:
            features = self.feature_repo.fetch_features(project_id)
            computed = len(features)
            insights = self.model_runner.compute(project_id, features)
            if self.ml_detector is not None:
                try:
                    insights.extend(self.ml_detector.detect_anomalies(project_id, features))
                except HANDLED_ML_DETECT_ERRORS:
                    # Fail-open: el flujo de insights no depende de ML.
                    pass
            now = datetime.now(timezone.utc)
            filtered: list = []
            shadowed_count = 0
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
                is_ml_insight = str(insight.rules_version).startswith("ml_") or str(insight.model_version).startswith("ml-")
                if self.ml_shadow_mode and is_ml_insight:
                    insight = replace(insight, status="shadow")
                    shadowed_count += 1
                filtered.append(
                    replace(
                        insight,
                        computed_by=computed_by,
                        job_run_id=job_run_id,
                    )
                )
            created = self.insight_repo.upsert_many(filtered)
            ml_created = sum(
                1
                for insight in filtered
                if str(insight.rules_version).startswith("ml_") or str(insight.model_version).startswith("ml-")
            )
            rules_created = max(created - ml_created, 0)
            if shadowed_count > 0 and self.metrics is not None:
                self.metrics.inc_counter("insights.compute.ml_shadow.count", shadowed_count)

            # Insights v2: análisis LLM + persistencia de propuesta (fail-open).
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
                params={
                    "project_id": project_id,
                    "rules_insights_created": rules_created,
                    "ml_insights_created": ml_created,
                },
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
            ml_insights_created=ml_created,
        )

    def _maybe_generate_proposal(self, *, project_id: str, insight) -> None:
        # Gating determinístico (antes del LLM).
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
            {
                "id": item.id,
                "type": item.type,
                "severity": item.severity,
                "status": item.status,
                "computed_at": item.computed_at.isoformat(),
                "title": item.title,
            }
            for item in history
            if item.id != insight.id
        ][:5]
        actions = self.insight_history.get_recent_actions(project_id, limit=5)
        previous_actions = [
            {
                "insight_id": a.insight_id,
                "user_id": a.user_id,
                "action": a.action,
                "created_at": a.created_at.isoformat(),
            }
            for a in actions
        ]
        historical_context = {
            "previous_insights": previous,
            "previous_actions": previous_actions,
            "outcomes": {},
        }

        prompt_version = getattr(self.insight_planner, "prompt_version", "unknown")
        tools_catalog_version = getattr(self.insight_planner, "tools_catalog_version", "unknown")
        provider_name = self.llm_provider or "unknown"
        model_name = self.llm_model or "unknown"

        try:
            proposal = self.insight_planner.plan(
                insight=insight,
                historical_context=historical_context,
                domain=self.domain,
                max_actions_allowed=self.max_actions_allowed,
            )
            self.proposal_store.insert(
                insight_id=insight.id,
                project_id=project_id,
                proposal=proposal,
                prompt_version=str(prompt_version),
                tools_catalog_version=str(tools_catalog_version),
                llm_provider=str(provider_name),
                llm_model=str(model_name),
                status="ok",
                error_message=None,
            )
        except HANDLED_PROPOSAL_ERRORS as exc:
            self.proposal_store.insert(
                insight_id=insight.id,
                project_id=project_id,
                proposal={},
                prompt_version=str(prompt_version),
                tools_catalog_version=str(tools_catalog_version),
                llm_provider=str(provider_name),
                llm_model=str(model_name),
                status="error",
                error_message=str(exc),
            )
