"""Servicio de insight_chat: resolución de snapshots y evidencia para follow-ups."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.insights.domain import Insight


class InsightEvidenceKPI(BaseModel):
    label: str
    value: str
    unit: str = ""
    trend: str = ""


class InsightEvidenceHighlight(BaseModel):
    severity: Literal["positive", "info", "warning"]
    title: str
    detail: str


class InsightEvidence(BaseModel):
    source: Literal["insight_handoff", "insight_chat_legacy_match"] = "insight_handoff"
    notification_id: str | None = None
    insight_id: str | None = None
    scope: str = ""
    computed_at: str = ""
    summary: str = ""
    kpis: list[InsightEvidenceKPI] = Field(default_factory=list)
    highlights: list[InsightEvidenceHighlight] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)


def build_insight_evidence_from_insight(
    insight: Insight,
    *,
    notification_id: str | None = None,
    source: Literal["insight_handoff", "insight_chat_legacy_match"] = "insight_handoff",
) -> InsightEvidence:
    """Construye evidencia de insight a partir de un Insight resuelto."""
    evidence_data = insight.evidence if isinstance(insight.evidence, dict) else {}
    action_data = insight.action if isinstance(insight.action, dict) else {}

    kpis: list[InsightEvidenceKPI] = []
    for key in ("feature", "feature_name"):
        if evidence_data.get(key):
            value = evidence_data.get("value", "")
            kpis.append(InsightEvidenceKPI(
                label=str(evidence_data[key]),
                value=str(value),
                unit=str(evidence_data.get("unit", "")),
                trend="up" if float(value or 0) > float(evidence_data.get("p75", 0) or 0) else "flat",
            ))
            break

    highlights: list[InsightEvidenceHighlight] = []
    if insight.severity >= 80:
        highlights.append(InsightEvidenceHighlight(
            severity="warning",
            title=insight.title,
            detail=insight.summary,
        ))
    elif insight.severity >= 50:
        highlights.append(InsightEvidenceHighlight(
            severity="info",
            title=insight.title,
            detail=insight.summary,
        ))

    recommendations: list[str] = []
    suggestion = action_data.get("suggestion")
    if suggestion:
        recommendations.append(str(suggestion))

    return InsightEvidence(
        source=source,
        notification_id=notification_id,
        insight_id=insight.id,
        scope=f"{insight.entity_type}:{insight.entity_id}",
        computed_at=insight.computed_at.isoformat() if insight.computed_at else datetime.now(UTC).isoformat(),
        summary=insight.summary,
        kpis=kpis,
        highlights=highlights,
        recommendations=recommendations,
        entity_ids=[insight.entity_id] if insight.entity_id else [],
    )


# --- Extracción y compactación para follow-ups ---

_EVIDENCE_TTL_HOURS = 24


def extract_insight_evidence(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Busca la evidencia de insight más reciente en los últimos 10 mensajes."""
    now = datetime.now(UTC)
    for item in reversed(messages[-10:]):
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        evidence = item.get("insight_evidence")
        if not isinstance(evidence, dict):
            continue
        computed_at = str(evidence.get("computed_at", "")).strip()
        if computed_at:
            try:
                ts = datetime.fromisoformat(computed_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if (now - ts).total_seconds() > _EVIDENCE_TTL_HOURS * 3600:
                    continue
            except (ValueError, TypeError):
                pass
        return evidence
    return None


def compact_insight_evidence_for_prompt(evidence: dict[str, Any]) -> str:
    """Compacta evidencia para inyectar en el prompt del LLM."""
    compacted: dict[str, Any] = {}
    for key in ("scope", "summary", "insight_id"):
        if evidence.get(key):
            compacted[key] = evidence[key]

    raw_kpis = evidence.get("kpis")
    if isinstance(raw_kpis, list):
        compacted["kpis"] = [
            {k: kpi[k] for k in ("label", "value", "unit", "trend") if k in kpi}
            for kpi in raw_kpis
        ]

    raw_highlights = evidence.get("highlights")
    if isinstance(raw_highlights, list):
        compacted["highlights"] = [
            {k: h[k] for k in ("severity", "title", "detail") if k in h}
            for h in raw_highlights
        ]

    raw_recs = evidence.get("recommendations")
    if isinstance(raw_recs, list):
        compacted["recommendations"] = list(raw_recs)

    result = json.dumps(compacted, ensure_ascii=False)
    # Truncar si es grande
    if len(result) > 2000:
        if "recommendations" in compacted:
            compacted["recommendations"] = compacted["recommendations"][:3]
        if "highlights" in compacted:
            compacted["highlights"] = compacted["highlights"][:5]
        result = json.dumps(compacted, ensure_ascii=False)

    return result
