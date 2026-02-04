import time
import uuid
from dataclasses import dataclass
import re
from typing import Any

from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from application.copilot.ports.insight_reader import InsightReaderPort, RelatedInsight
from application.copilot.ports.copilot_explainer import CopilotExplainMode
from application.copilot.use_cases.explain_insight import ExplainInsight


_UUID_RE = re.compile(
    r"(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


@dataclass(frozen=True)
class AskResult:
    request_id: str
    intent: str
    query_id: str | None
    params: dict[str, Any]
    data: list[dict[str, Any]]
    answer: str
    sources: list[dict[str, Any]]
    warnings: list[str]
    related_insights_count: int
    related_insights: list[RelatedInsight]


class AskCopilot:
    def __init__(
        self,
        explain_insight: ExplainInsight,
        audit_logger: AuditLoggerPort,
        insight_reader: InsightReaderPort,
    ) -> None:
        self.explain_insight = explain_insight
        self.audit_logger = audit_logger
        self.insight_reader = insight_reader

    def handle(
        self,
        question: str,
        context: dict[str, Any] | None,
        user_id: str,
        project_id: str,
    ) -> AskResult:
        request_id = str(uuid.uuid4())
        started = time.time()

        warnings: list[str] = []
        data: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        params: dict[str, Any] = {"project_id": project_id}
        if context:
            # Se conserva por compatibilidad, pero Copilot v2 no explora datos por ventana.
            if context.get("date_from"):
                params["date_from"] = context["date_from"]
            if context.get("date_to"):
                params["date_to"] = context["date_to"]

        insight_id = _extract_uuid(question)
        intent = "explainability"
        query_id = None

        try:
            if not insight_id:
                # Copilot v2: no hay chat libre. Respuesta determinística (deprecación controlada).
                warnings.append("Copilot v2: /v1/ask ya no soporta chat libre. Usá endpoints /v1/copilot/... para explainability.")
                answer = "Copilot v2 solo explica insights existentes. Proveé un insight_id para obtener explicación."
                intent = "deprecated"
            else:
                mode = _infer_mode(question)
                params["insight_id"] = insight_id
                params["mode"] = mode
                result = self.explain_insight.handle(project_id=project_id, insight_id=insight_id, mode=mode)
                answer = result["explanation"]["human_readable"]
                sources.append({"type": "insight", "insight_id": insight_id})
                sources.append({"type": "proposal", "available": result.get("proposal") is not None})

            duration_ms = int((time.time() - started) * 1000)
            self.audit_logger.log(
                AuditRecord(
                    request_id=request_id,
                    user_id=user_id,
                    project_id=project_id,
                    question=question,
                    intent=intent,
                    query_id=query_id,
                    params=params,
                    duration_ms=duration_ms,
                    rows_count=len(data),
                    status="ok",
                    error=None,
                )
            )

            related_count = self.insight_reader.count_active(project_id)
            related_items = self.insight_reader.list_active(project_id, limit=3)
            return AskResult(
                request_id=request_id,
                intent=intent,
                query_id=query_id,
                params=params,
                data=data,
                answer=answer,
                sources=sources,
                warnings=warnings,
                related_insights_count=related_count,
                related_insights=related_items,
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.time() - started) * 1000)
            self.audit_logger.log(
                AuditRecord(
                    request_id=request_id,
                    user_id=user_id,
                    project_id=project_id,
                    question=question,
                    intent=intent,
                    query_id=query_id,
                    params=params,
                    duration_ms=duration_ms,
                    rows_count=0,
                    status="error",
                    error=str(exc),
                )
            )
            return AskResult(
                request_id=request_id,
                intent=intent,
                query_id=query_id,
                params=params,
                data=[],
                answer="Error procesando la consulta.",
                sources=sources,
                warnings=warnings + [str(exc)],
                related_insights_count=0,
                related_insights=[],
            )


def _extract_uuid(text: str) -> str | None:
    match = _UUID_RE.search(text)
    if not match:
        return None
    return match.group("uuid")


def _infer_mode(question: str) -> CopilotExplainMode:
    q = question.lower()
    if any(token in q for token in ["por qué", "por que", "why", "causa"]):
        return "why"
    if any(token in q for token in ["next", "próximo", "proximo", "siguientes", "pasos"]):
        return "next_steps"
    return "explain"
