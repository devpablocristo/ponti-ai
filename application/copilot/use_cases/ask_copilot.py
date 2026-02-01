import time
import uuid
from dataclasses import dataclass
from typing import Any

from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from application.copilot.ports.intent_classifier import IntentClassifierPort
from application.copilot.ports.rag_repository import RagRepositoryPort
from application.copilot.ports.sql_catalog import SQLCatalogPort
from application.copilot.ports.sql_executor import SQLExecutorPort
from app.config import Settings


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


class AskCopilot:
    def __init__(
        self,
        settings: Settings,
        intent_classifier: IntentClassifierPort,
        sql_catalog: SQLCatalogPort,
        sql_executor: SQLExecutorPort,
        rag_repo: RagRepositoryPort,
        audit_logger: AuditLoggerPort,
    ) -> None:
        self.settings = settings
        self.intent_classifier = intent_classifier
        self.sql_catalog = sql_catalog
        self.sql_executor = sql_executor
        self.rag_repo = rag_repo
        self.audit_logger = audit_logger

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
            if context.get("date_from"):
                params["date_from"] = context["date_from"]
            if context.get("date_to"):
                params["date_to"] = context["date_to"]

        intent_decision = self.intent_classifier.classify(question, params)
        intent = intent_decision.intent
        query_id = intent_decision.query_id

        try:
            if intent == "docs":
                rag_results = self.rag_repo.search(project_id, question)
                sources.append({"type": "rag", "doc_ids": rag_results.doc_ids, "top_k": rag_results.top_k})
                answer = rag_results.answer
                data = []
            else:
                if not query_id:
                    warnings.append("No se pudo determinar query_id para la pregunta.")
                    answer = "No se pudo resolver la consulta solicitada."
                else:
                    entry = self.sql_catalog.get_entry(query_id)
                    params = entry.validate_params(params)
                    if not entry.implemented:
                        warnings.append("Query no implementada: falta schema real.")
                        answer = "Query no implementada en el MVP."
                    else:
                        data = self.sql_executor.execute(
                            sql_template=entry.sql_template,
                            params=params,
                            statement_timeout_ms=self.settings.statement_timeout_ms,
                            max_limit=self.settings.max_limit,
                            default_limit=self.settings.default_limit,
                        )
                        answer = "Consulta ejecutada correctamente."
                    sources.append({"type": "sql", "query_id": query_id, "params": params})

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

            return AskResult(
                request_id=request_id,
                intent=intent,
                query_id=query_id,
                params=params,
                data=data,
                answer=answer,
                sources=sources,
                warnings=warnings,
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
            )
