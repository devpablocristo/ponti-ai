"""Helpers para reusar evidencia de insights ya inyectada en mensajes anteriores
del mismo chat (follow-ups). El path de resolución contra la DB local quedó muerto
cuando los insights se movieron a ponti-backend; lo único que sigue vivo es leer
el `insight_evidence` que el agente haya guardado en mensajes previos."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

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
    if len(result) > 2000:
        if "recommendations" in compacted:
            compacted["recommendations"] = compacted["recommendations"][:3]
        if "highlights" in compacted:
            compacted["highlights"] = compacted["highlights"][:5]
        result = json.dumps(compacted, ensure_ascii=False)

    return result
