import json
from dataclasses import dataclass
from typing import Any

from application.copilot.ports.intent_classifier import IntentDecision


INTENT_SYSTEM_PROMPT = (
    "Sos un clasificador estricto. Respondé solo JSON válido "
    "con las claves: intent, query_id, params. "
    "intent debe ser docs, metrics o analysis. "
    "No incluyas texto adicional."
)


def _is_docs_question(question: str) -> bool:
    q = question.lower()
    return any(token in q for token in ["documento", "manual", "guia", "readme", "doc"])


@dataclass(frozen=True)
class LLMResponse:
    raw_json: str


class IntentClassifier:
    def classify(self, question: str, params: dict[str, Any]) -> IntentDecision:
        if _is_docs_question(question):
            return IntentDecision(intent="docs", query_id=None, params=params)

        response = self._classify_stub(question)
        try:
            payload = json.loads(response.raw_json)
        except json.JSONDecodeError:
            return IntentDecision(intent="metrics", query_id="project_overview", params=params)

        intent = payload.get("intent", "metrics")
        query_id = payload.get("query_id", "project_overview")
        payload_params = payload.get("params", {})
        merged = {**params, **payload_params}

        return IntentDecision(intent=intent, query_id=query_id, params=merged)

    def _classify_stub(self, question: str) -> LLMResponse:
        intent = "metrics"
        query_id = "project_overview"
        if "analisis" in question.lower():
            intent = "analysis"
        payload = {
            "intent": intent,
            "query_id": query_id,
            "params": {},
        }
        return LLMResponse(raw_json=json.dumps(payload))
