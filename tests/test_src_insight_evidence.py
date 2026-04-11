"""Tests para insight_chat_service: evidencia, extracción y compactación."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.agents.insight_chat_service import (
    InsightEvidence,
    _EVIDENCE_TTL_HOURS,
    build_insight_evidence_from_insight,
    compact_insight_evidence_for_prompt,
    extract_insight_evidence,
)
from src.insights.domain import Insight


def _make_insight(insight_id: str = "ins-1", severity: int = 80) -> Insight:
    now = datetime.now(UTC)
    return Insight(
        id=insight_id, project_id="p1", entity_type="project", entity_id="p1",
        type="anomaly", severity=severity, priority=severity,
        title="Alerta de costo", summary="Costo fuera de rango.",
        evidence={"feature": "cost_total", "n_samples": 60, "value": 40.0, "p75": 30.0},
        explanations={"rule": "test"}, action={"suggestion": "Revisar costos"},
        model_version="test", features_version="test",
        computed_at=now, valid_until=now + timedelta(days=7), status="new",
    )


# --- build_insight_evidence_from_insight ---


def test_build_evidence_from_insight() -> None:
    insight = _make_insight()
    evidence = build_insight_evidence_from_insight(insight, notification_id="notif-1")
    assert evidence.source == "insight_handoff"
    assert evidence.notification_id == "notif-1"
    assert evidence.insight_id == "ins-1"
    assert evidence.scope == "project:p1"
    assert evidence.summary == "Costo fuera de rango."
    assert len(evidence.kpis) >= 1
    assert evidence.kpis[0].label == "cost_total"
    assert len(evidence.highlights) >= 1
    assert evidence.highlights[0].severity == "warning"
    assert len(evidence.recommendations) >= 1
    assert "Revisar costos" in evidence.recommendations[0]


def test_build_evidence_low_severity_gets_info_highlight() -> None:
    insight = _make_insight(severity=60)
    evidence = build_insight_evidence_from_insight(insight)
    assert evidence.highlights[0].severity == "info"


def test_build_evidence_serializable() -> None:
    evidence = build_insight_evidence_from_insight(_make_insight())
    dumped = evidence.model_dump(mode="json")
    assert isinstance(dumped, dict)
    assert dumped["source"] == "insight_handoff"
    restored = InsightEvidence.model_validate(dumped)
    assert restored.insight_id == "ins-1"


# --- extract_insight_evidence ---


def _assistant_msg(evidence: dict | None = None) -> dict:
    msg: dict = {"role": "assistant", "content": "Respuesta."}
    if evidence is not None:
        msg["insight_evidence"] = evidence
    return msg


def _user_msg(text: str = "pregunta") -> dict:
    return {"role": "user", "content": text}


def test_extract_returns_none_for_empty() -> None:
    assert extract_insight_evidence([]) is None


def test_extract_returns_none_when_no_evidence() -> None:
    messages = [_user_msg(), _assistant_msg(None)]
    assert extract_insight_evidence(messages) is None


def test_extract_returns_latest_evidence() -> None:
    old_ev = {"scope": "old", "computed_at": datetime.now(UTC).isoformat()}
    new_ev = {"scope": "new", "computed_at": datetime.now(UTC).isoformat()}
    messages = [_assistant_msg(old_ev), _user_msg(), _assistant_msg(new_ev)]
    result = extract_insight_evidence(messages)
    assert result is not None
    assert result["scope"] == "new"


def test_extract_ignores_user_messages() -> None:
    fake = {"role": "user", "content": "hola", "insight_evidence": {"scope": "fake"}}
    messages = [fake, _assistant_msg(None)]
    assert extract_insight_evidence(messages) is None


def test_extract_respects_24h_expiration() -> None:
    old_ts = (datetime.now(UTC) - timedelta(hours=_EVIDENCE_TTL_HOURS + 1)).isoformat()
    evidence = {"scope": "old", "computed_at": old_ts}
    messages = [_assistant_msg(evidence)]
    assert extract_insight_evidence(messages) is None


# --- compact_insight_evidence_for_prompt ---


def test_compact_excludes_entity_ids() -> None:
    evidence = build_insight_evidence_from_insight(_make_insight()).model_dump(mode="json")
    result = compact_insight_evidence_for_prompt(evidence)
    parsed = json.loads(result)
    assert "entity_ids" not in parsed
    assert "notification_id" not in parsed
    assert "source" not in parsed


def test_compact_includes_kpis() -> None:
    evidence = build_insight_evidence_from_insight(_make_insight()).model_dump(mode="json")
    result = compact_insight_evidence_for_prompt(evidence)
    parsed = json.loads(result)
    assert "kpis" in parsed
    assert len(parsed["kpis"]) >= 1
    assert "label" in parsed["kpis"][0]


def test_compact_truncates_when_large() -> None:
    evidence = build_insight_evidence_from_insight(_make_insight()).model_dump(mode="json")
    evidence["highlights"] = [{"severity": "info", "title": f"H{i}", "detail": "x" * 200} for i in range(20)]
    evidence["recommendations"] = [f"Rec {i} " + "x" * 100 for i in range(15)]
    result = compact_insight_evidence_for_prompt(evidence)
    parsed = json.loads(result)
    assert len(parsed.get("recommendations", [])) <= 3
    assert len(parsed.get("highlights", [])) <= 5
