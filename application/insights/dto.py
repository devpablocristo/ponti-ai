from dataclasses import dataclass


@dataclass(frozen=True)
class ComputeInsightsResult:
    request_id: str
    computed: int
    insights_created: int
    rules_insights_created: int
    ml_insights_created: int


@dataclass(frozen=True)
class RecordActionResult:
    request_id: str


@dataclass(frozen=True)
class RecomputeActiveResult:
    status: str
    job_run_id: str


@dataclass(frozen=True)
class RecomputeBaselinesResult:
    status: str
    job_run_id: str
    cohort_saved: int
    project_saved: int


@dataclass(frozen=True)
class QueueRecomputeEventResult:
    status: str
    project_id: str


@dataclass(frozen=True)
class ProcessQueueItemResult:
    status: str
    project_id: str


@dataclass(frozen=True)
class ProcessRecomputeQueueResult:
    claimed: int
    processed: int
    ok: int
    locked: int
    errors: int
