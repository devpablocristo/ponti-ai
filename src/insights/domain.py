"""Entidades mínimas usadas por el dossier del chat (`get_summary`)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopInsight:
    id: str
    title: str
    severity: int
    status: str


@dataclass(frozen=True)
class InsightSummary:
    new_count_total: int
    new_count_high_severity: int
    top_insights: list[TopInsight]
