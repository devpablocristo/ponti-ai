from contexts.insights.application.use_cases.recompute_active import RecomputeActive


class FakeComputeInsights:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def handle(
        self,
        project_id: str,
        user_id: str,
        computed_by: str = "on_demand",
        job_run_id: str | None = None,
        max_features: int | None = None,
    ):
        self.calls.append(
            {
                "project_id": project_id,
                "user_id": user_id,
                "computed_by": computed_by,
                "job_run_id": job_run_id,
                "max_features": max_features,
            }
        )
        return None


class FakeInsightRepo:
    def __init__(self) -> None:
        self.recomputed_project_id: str | None = None

    def mark_recomputed(self, project_id: str) -> None:
        self.recomputed_project_id = project_id


class FakeJobLock:
    def __init__(self, can_lock: bool = True) -> None:
        self.can_lock = can_lock
        self.released = False

    def try_lock(self, key: int) -> bool:
        _ = key
        return self.can_lock

    def release(self, key: int) -> None:
        _ = key
        self.released = True


def test_recompute_active_returns_locked_when_cannot_acquire_lock() -> None:
    use_case = RecomputeActive(
        compute_insights=FakeComputeInsights(),  # type: ignore[arg-type]
        insight_repo=FakeInsightRepo(),  # type: ignore[arg-type]
        job_lock=FakeJobLock(can_lock=False),  # type: ignore[arg-type]
    )

    result = use_case.handle(project_id="p1", lock_key=41002, batch_size=50)

    assert result.status == "locked"
    assert result.job_run_id == ""


def test_recompute_active_passes_batch_size_as_max_features() -> None:
    compute = FakeComputeInsights()
    repo = FakeInsightRepo()
    lock = FakeJobLock(can_lock=True)
    use_case = RecomputeActive(
        compute_insights=compute,  # type: ignore[arg-type]
        insight_repo=repo,  # type: ignore[arg-type]
        job_lock=lock,  # type: ignore[arg-type]
    )

    result = use_case.handle(project_id="p1", lock_key=41002, batch_size=25)

    assert result.status == "ok"
    assert result.job_run_id != ""
    assert repo.recomputed_project_id == "p1"
    assert lock.released is True
    assert compute.calls[0]["max_features"] == 25

