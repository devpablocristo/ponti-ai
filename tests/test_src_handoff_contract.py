"""Tests de parsing del contrato ChatHandoff y backward compat."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.chat_contract import ChatHandoff, ChatRequest


# --- ChatHandoff parsing ---


def test_handoff_parses_full_payload() -> None:
    h = ChatHandoff(
        source="in_app_notification",
        notification_id="notif-1",
        insight_id="ins-1",
        insight_scope="project:p1",
        period="month",
    )
    assert h.source == "in_app_notification"
    assert h.notification_id == "notif-1"
    assert h.insight_id == "ins-1"
    assert h.insight_scope == "project:p1"
    assert h.period == "month"


def test_handoff_parses_minimal_payload() -> None:
    h = ChatHandoff(source="direct")
    assert h.source == "direct"
    assert h.notification_id is None
    assert h.insight_id is None


def test_handoff_rejects_invalid_source() -> None:
    with pytest.raises(ValidationError):
        ChatHandoff(source="unknown_source")


def test_handoff_rejects_empty_notification_id() -> None:
    with pytest.raises(ValidationError):
        ChatHandoff(source="in_app_notification", notification_id="")


# --- ChatRequest backward compat ---


def test_chat_request_without_handoff() -> None:
    req = ChatRequest(message="hola")
    assert req.handoff is None
    assert req.route_hint is None
    assert req.chat_id is None
    assert req.confirmed_actions == []


def test_chat_request_with_handoff() -> None:
    req = ChatRequest(
        message="explicame este insight",
        handoff={
            "source": "in_app_notification",
            "notification_id": "notif-1",
            "insight_id": "ins-1",
        },
        route_hint="insight_chat",
    )
    assert req.handoff is not None
    assert req.handoff.source == "in_app_notification"
    assert req.handoff.notification_id == "notif-1"
    assert req.route_hint == "insight_chat"


def test_chat_request_with_route_hint_only() -> None:
    req = ChatRequest(message="mostrame labores", route_hint="labors")
    assert req.handoff is None
    assert req.route_hint == "labors"


def test_chat_request_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_request_serialization_roundtrip() -> None:
    req = ChatRequest(
        message="test",
        handoff=ChatHandoff(source="direct", insight_id="ins-1"),
    )
    dumped = req.model_dump(mode="json")
    assert dumped["handoff"]["source"] == "direct"
    assert dumped["handoff"]["insight_id"] == "ins-1"
    restored = ChatRequest(**dumped)
    assert restored.handoff.insight_id == "ins-1"
