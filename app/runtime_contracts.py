"""Compatibilidad local para contratos compartidos de AI."""

from __future__ import annotations

try:
    from runtime import (
        OUTPUT_KIND_COPILOT_EXPLANATION,
        OUTPUT_KIND_INSIGHT_SUMMARY,
        ROUTING_SOURCE_COPILOT_AGENT,
        SERVICE_KIND_INSIGHT,
    )
except ImportError:
    OUTPUT_KIND_COPILOT_EXPLANATION = "copilot_explanation"
    OUTPUT_KIND_INSIGHT_SUMMARY = "insight_summary"
    ROUTING_SOURCE_COPILOT_AGENT = "copilot_agent"
    SERVICE_KIND_INSIGHT = "insight_service"

__all__ = [
    "OUTPUT_KIND_COPILOT_EXPLANATION",
    "OUTPUT_KIND_INSIGHT_SUMMARY",
    "ROUTING_SOURCE_COPILOT_AGENT",
    "SERVICE_KIND_INSIGHT",
]
