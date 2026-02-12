from datetime import datetime, timezone

from application.insights.ports.baseline_computer import BaselineComputerPort, CohortConfig
from application.insights.ports.baseline_repository import BaselineRecord, BaselineRepositoryPort
from application.insights.ports.job_lock import JobLockPort
from application.insights.ports.project_repository import ProjectRepositoryPort
from application.insights.use_cases.recompute_baselines import RecomputeBaselines
from adapters.outbound.models.anomaly_runner import AnomalyRunner
from application.insights.ports.feature_repository import FeatureValue


class FakeBaselineRepo(BaselineRepositoryPort):
    def __init__(self) -> None:
        self.records: list[BaselineRecord] = []

    def upsert_many(self, records: list[BaselineRecord]) -> int:
        self.records.extend(records)
        return len(records)

    def get_baseline(
        self,
        scope_type: str,
        scope_id: str | None,
        cohort_key: str,
        feature_name: str,
        window: str,
    ) -> BaselineRecord | None:
        for record in self.records:
            if (
                record.scope_type == scope_type
                and record.scope_id == scope_id
                and record.cohort_key == cohort_key
                and record.feature_name == feature_name
                and record.window == window
            ):
                return record
        return None


class FakeBaselineComputer(BaselineComputerPort):
    def __init__(self) -> None:
        self.last_cohort: CohortConfig | None = None

    def compute_cohort_baselines(self, project_id: str, cohort: CohortConfig) -> list[BaselineRecord]:
        self.last_cohort = cohort
        return [
            BaselineRecord(
                scope_type="global",
                scope_id=None,
                cohort_key="size=small",
                feature_name="cost_total",
                window="all",
                p50=10.0,
                p75=20.0,
                p90=30.0,
                n_samples=50,
                computed_at=datetime.now(timezone.utc),
            )
        ]

    def compute_project_baselines(self, project_id: str, baseline_days: int, min_samples: int) -> list[BaselineRecord]:
        _ = baseline_days
        _ = min_samples
        return [
            BaselineRecord(
                scope_type="project",
                scope_id=project_id,
                cohort_key="self",
                feature_name="cost_total",
                window="all",
                p50=8.0,
                p75=12.0,
                p90=16.0,
                n_samples=20,
                computed_at=datetime.now(timezone.utc),
            )
        ]


class FakeProjectRepo(ProjectRepositoryPort):
    def __init__(self) -> None:
        self.calls = 0

    def list_project_ids(self, project_id: str, start_after_id: int | None, limit: int) -> list[int]:
        _ = project_id
        _ = limit
        self.calls += 1
        if start_after_id is None:
            return [1, 2]
        return []


class FakeJobLock(JobLockPort):
    def __init__(self, locked: bool = False) -> None:
        self.locked = locked
        self.acquired = False

    def try_lock(self, key: int) -> bool:
        _ = key
        if self.locked:
            return False
        self.acquired = True
        return True

    def release(self, key: int) -> None:
        _ = key
        self.acquired = False


def test_recompute_baselines_lock() -> None:
    use_case = RecomputeBaselines(
        baseline_computer=FakeBaselineComputer(),
        baseline_repo=FakeBaselineRepo(),
        project_repo=FakeProjectRepo(),
        job_lock=FakeJobLock(locked=True),
    )
    result = use_case.handle(
        project_id="p1",
        cohort=CohortConfig(size_small_max=200, size_medium_max=1000),
        baseline_days=365,
        min_samples=10,
        batch_size=100,
        lock_key=1,
    )
    assert result.status == "locked"


def test_recompute_baselines_uses_cohort_and_projects() -> None:
    baseline_repo = FakeBaselineRepo()
    baseline_computer = FakeBaselineComputer()
    project_repo = FakeProjectRepo()
    job_lock = FakeJobLock()

    use_case = RecomputeBaselines(
        baseline_computer=baseline_computer,
        baseline_repo=baseline_repo,
        project_repo=project_repo,
        job_lock=job_lock,
    )
    result = use_case.handle(
        project_id="p1",
        cohort=CohortConfig(size_small_max=200, size_medium_max=1000),
        baseline_days=365,
        min_samples=10,
        batch_size=100,
        lock_key=1,
    )
    assert result.status == "ok"
    assert baseline_computer.last_cohort is not None
    assert baseline_computer.last_cohort.size_small_max == 200
    assert baseline_computer.last_cohort.size_medium_max == 1000
    assert result.cohort_saved == 1
    assert result.project_saved == 2


def test_anomaly_runner_fallback_to_cohort() -> None:
    baseline_repo = FakeBaselineRepo()
    baseline_repo.upsert_many(
        [
            BaselineRecord(
                scope_type="global",
                scope_id=None,
                cohort_key="size=small",
                feature_name="cost_total",
                window="all",
                p50=10.0,
                p75=20.0,
                p90=30.0,
                n_samples=25,
                computed_at=datetime.now(timezone.utc),
            )
        ]
    )
    runner = AnomalyRunner(
        baseline_repo=baseline_repo,
        ratio_high=0.5,
        ratio_medium=0.2,
        spike_ratio=1.5,
        size_small_max=200,
        size_medium_max=1000,
        cooldown_days=7,
        impact_k=1.0,
        impact_cap=2.0,
    )
    features = [
        FeatureValue(
            project_id="p1",
            entity_type="project",
            entity_id="p1",
            feature_name="total_hectares",
            window="all",
            value=150,
        ),
        FeatureValue(
            project_id="p1",
            entity_type="project",
            entity_id="p1",
            feature_name="cost_total",
            window="all",
            value=35.0,
        ),
    ]
    insights = runner.compute("p1", features)
    assert insights
    assert insights[0].evidence["baseline_scope"] == "cohort"
