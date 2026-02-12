from datetime import datetime, timezone

from adapters.outbound.sql.baseline_catalog import list_cohort_queries, list_project_queries
from adapters.outbound.sql.executor import SQLExecutor
from app.config import Settings
from contexts.insights.application.ports.baseline_computer import BaselineComputerPort, CohortConfig
from contexts.insights.application.ports.baseline_repository import BaselineRecord


class BaselineComputerPG(BaselineComputerPort):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = SQLExecutor(settings)

    def compute_cohort_baselines(
        self,
        project_id: str,
        cohort: CohortConfig,
    ) -> list[BaselineRecord]:
        records: list[BaselineRecord] = []
        for entry in list_cohort_queries():
            rows = self.executor.execute(
                sql_template=entry.sql_template,
                params={
                    "project_id": project_id,
                    "limit": self.settings.max_limit,
                    "size_small_max": cohort.size_small_max,
                    "size_medium_max": cohort.size_medium_max,
                },
                statement_timeout_ms=self.settings.statement_timeout_ms,
                max_limit=self.settings.max_limit,
                default_limit=self.settings.default_limit,
            )
            for row in rows:
                records.append(
                    BaselineRecord(
                        scope_type="global",
                        scope_id=None,
                        cohort_key=row.get("cohort_key", "size=unknown"),
                        feature_name=row.get("feature_name", entry.feature_name),
                        window=row.get("window_name", entry.window),
                        p50=float(row.get("p50", 0.0)),
                        p75=float(row.get("p75", 0.0)),
                        p90=float(row.get("p90", 0.0)),
                        n_samples=int(row.get("n_samples", 0)),
                        computed_at=datetime.now(timezone.utc),
                    )
                )
        return records

    def compute_project_baselines(
        self,
        project_id: str,
        baseline_days: int,
        min_samples: int,
    ) -> list[BaselineRecord]:
        records: list[BaselineRecord] = []
        for entry in list_project_queries():
            rows = self.executor.execute(
                sql_template=entry.sql_template,
                params={
                    "project_id": project_id,
                    "baseline_days": baseline_days,
                    "limit": self.settings.default_limit,
                },
                statement_timeout_ms=self.settings.statement_timeout_ms,
                max_limit=self.settings.max_limit,
                default_limit=self.settings.default_limit,
            )
            for row in rows:
                n_samples = int(row.get("n_samples", 0))
                if n_samples < min_samples:
                    continue
                records.append(
                    BaselineRecord(
                        scope_type="project",
                        scope_id=project_id,
                        cohort_key=row.get("cohort_key", "self"),
                        feature_name=row.get("feature_name", entry.feature_name),
                        window=row.get("window_name", entry.window),
                        p50=float(row.get("p50", 0.0)),
                        p75=float(row.get("p75", 0.0)),
                        p90=float(row.get("p90", 0.0)),
                        n_samples=n_samples,
                        computed_at=datetime.now(timezone.utc),
                    )
                )
        return records
