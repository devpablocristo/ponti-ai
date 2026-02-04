from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from application.copilot.ports.insight_reader import InsightReaderPort, RelatedInsight
from application.copilot.use_cases.ask_copilot import AskCopilot
from application.copilot.use_cases.explain_insight import ExplainInsight


class FakeExplainInsight(ExplainInsight):
    def __init__(self) -> None:
        pass

    def handle(self, *, project_id: str, insight_id: str, mode: str):  # type: ignore[override]
        _ = project_id
        return {
            "insight_id": insight_id,
            "mode": mode,
            "explanation": {
                "human_readable": f"Expl:{mode}:{insight_id}",
                "audit_focused": "audit",
                "what_to_watch_next": "watch",
            },
            "proposal": {"decision_summary": {"recommended_outcome": "propose_actions"}},
        }


class FakeAudit(AuditLoggerPort):
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def log(self, record: AuditRecord) -> None:
        self.records.append(record)


class FakeReader(InsightReaderPort):
    def count_active(self, project_id: str) -> int:
        _ = project_id
        return 0

    def list_active(self, project_id: str, limit: int) -> list[RelatedInsight]:
        _ = project_id
        _ = limit
        return []


def test_ask_copilot_v2_extracts_uuid_and_calls_explainer() -> None:
    audit = FakeAudit()
    copilot = AskCopilot(explain_insight=FakeExplainInsight(), audit_logger=audit, insight_reader=FakeReader())
    res = copilot.handle(
        question="Por qué es importante el insight 7e1bdc3e-6ec0-5814-9d7d-50c1d3486612?",
        context=None,
        user_id="u1",
        project_id="p1",
    )
    assert res.intent == "explainability"
    assert res.query_id is None
    assert res.answer.startswith("Expl:why:7e1bdc3e-6ec0-5814-9d7d-50c1d3486612")
    assert audit.records


def test_ask_copilot_v2_no_chat_without_insight_id() -> None:
    audit = FakeAudit()
    copilot = AskCopilot(explain_insight=FakeExplainInsight(), audit_logger=audit, insight_reader=FakeReader())
    res = copilot.handle(
        question="Necesito el resumen del proyecto",
        context=None,
        user_id="u1",
        project_id="p1",
    )
    assert res.intent == "deprecated"
    assert res.data == []
    assert "no soporta chat libre" in " ".join(res.warnings).lower()

