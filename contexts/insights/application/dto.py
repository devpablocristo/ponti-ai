from dataclasses import dataclass


@dataclass(frozen=True)
class ComputeInsightsResult:
    request_id: str
    computed: int
    insights_created: int
    rules_insights_created: int


@dataclass(frozen=True)
class RecordActionResult:
    request_id: str
