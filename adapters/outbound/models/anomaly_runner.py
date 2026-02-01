import uuid
from datetime import datetime, timedelta, timezone

from application.insights.ports.baseline_repository import BaselineRepositoryPort
from application.insights.ports.feature_repository import FeatureValue
from domain.insights.entities import Insight


class AnomalyRunner:
    def __init__(
        self,
        baseline_repo: BaselineRepositoryPort,
        model_version: str = "baseline-v1",
        features_version: str = "features-v1",
        ratio_high: float = None,
        ratio_medium: float = None,
        spike_ratio: float = None,
        size_small_max: float = None,
        size_medium_max: float = None,
        cooldown_days: int = None,
        impact_k: float = None,
        impact_cap: float = None,
    ) -> None:
        self.baseline_repo = baseline_repo
        self.model_version = model_version
        self.features_version = features_version
        if ratio_high is None or ratio_medium is None or spike_ratio is None:
            raise ValueError("ratios de insights son requeridos")
        if size_small_max is None or size_medium_max is None:
            raise ValueError("tamanos de cohortes son requeridos")
        if cooldown_days is None or impact_k is None or impact_cap is None:
            raise ValueError("config de cooldown/impacto es requerida")
        self.ratio_high = ratio_high
        self.ratio_medium = ratio_medium
        self.spike_ratio = spike_ratio
        self.size_small_max = size_small_max
        self.size_medium_max = size_medium_max
        self.cooldown_days = cooldown_days
        self.impact_k = impact_k
        self.impact_cap = impact_cap

    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        now = datetime.now(timezone.utc)
        insights: list[Insight] = []
        cooldown_until = now + timedelta(days=self.cooldown_days)

        total_hectares = None
        for f in features:
            if f.entity_type == "project" and f.feature_name == "total_hectares" and f.window == "all":
                total_hectares = f.value
                break

        cohort_key = "size=unknown"
        if total_hectares is not None:
            if total_hectares <= self.size_small_max:
                cohort_key = "size=small"
            elif total_hectares <= self.size_medium_max:
                cohort_key = "size=medium"
            else:
                cohort_key = "size=large"

        feature_map: dict[tuple[str, str], FeatureValue] = {
            (f.feature_name, f.window): f for f in features if f.entity_type == "project"
        }

        for feature in features:
            if feature.entity_type != "project":
                continue

            baseline = self.baseline_repo.get_baseline(
                scope_type="project",
                scope_id=project_id,
                cohort_key="self",
                feature_name=feature.feature_name,
                window=feature.window,
            )
            baseline_scope = "project"
            if baseline is None:
                baseline = self.baseline_repo.get_baseline(
                    scope_type="global",
                    scope_id=None,
                    cohort_key=cohort_key,
                    feature_name=feature.feature_name,
                    window=feature.window,
                )
                baseline_scope = "cohort"
            if baseline is None:
                baseline = self.baseline_repo.get_baseline(
                    scope_type="global",
                    scope_id=None,
                    cohort_key=cohort_key,
                    feature_name=feature.feature_name,
                    window="all",
                )
                baseline_scope = "cohort"
            if baseline is None:
                continue

            if feature.value >= baseline.p90:
                insight_type = "anomaly"
                severity = 80
                delta_ratio = (feature.value - baseline.p90) / baseline.p90 if baseline.p90 else 0
            elif feature.value >= baseline.p75:
                insight_type = "recommendation"
                severity = 40
                delta_ratio = (feature.value - baseline.p75) / baseline.p75 if baseline.p75 else 0
            else:
                continue

            title = f"{feature.feature_name} alto vs baseline"
            summary = (
                f"Valor {feature.value} vs p75 {baseline.p75} y p90 {baseline.p90} "
                f"({baseline_scope}, {cohort_key})."
            )

            impact_pct = min(max(delta_ratio * self.impact_k, 0.0), self.impact_cap)
            impact_min = impact_pct * 0.7
            impact_max = impact_pct * 1.3
            confidence = "high" if baseline.n_samples >= 50 else "medium" if baseline.n_samples >= 20 else "low"

            if feature.feature_name in ("inputs_total_used", "stock_variance"):
                action_type = "inventory_check"
                cta_label = "Revisar stock"
            elif feature.feature_name in ("cost_total", "cost_per_ha"):
                action_type = "review_inputs"
                cta_label = "Revisar costos"
            else:
                action_type = "checklist"
                cta_label = "Revisar"

            dedupe_key = f"{feature.feature_name}:{feature.window}:{insight_type}"
            stable_key = (
                f"{project_id}|{feature.entity_type}|{feature.entity_id}|"
                f"{feature.feature_name}|{feature.window}|{insight_type}"
            )
            insights.append(
                Insight(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key)),
                    project_id=project_id,
                    entity_type=feature.entity_type,
                    entity_id=feature.entity_id,
                    type=insight_type,
                    severity=severity,
                    priority=severity,
                    title=title,
                    summary=summary,
                    evidence={
                        "feature": feature.feature_name,
                        "window": feature.window,
                        "value": feature.value,
                        "baseline_scope": baseline_scope,
                        "cohort_key": cohort_key,
                        "p75": baseline.p75,
                        "p90": baseline.p90,
                        "n_samples": baseline.n_samples,
                    },
                    explanations={"rule": "baseline_percentile"},
                    action={
                        "action_type": action_type,
                        "action_params": {"feature": feature.feature_name, "window": feature.window},
                        "suggested_due_date": (now + timedelta(days=7)).date().isoformat(),
                        "cta_label": cta_label,
                    },
                    model_version=self.model_version,
                    features_version=self.features_version,
                    computed_at=now,
                    valid_until=now + timedelta(days=7),
                    status="new",
                    impact_min=impact_min,
                    impact_max=impact_max,
                    impact_unit="%",
                    confidence=confidence,
                    dedupe_key=dedupe_key,
                    cooldown_until=cooldown_until,
                    rules_version="v2",
                )
            )

        for base_name in ["cost_total", "inputs_total_used", "workorders_count"]:
            last_7 = feature_map.get((base_name, "last_7d"))
            last_30 = feature_map.get((base_name, "last_30d"))
            if not last_7 or not last_30 or last_30.value <= 0:
                continue
            expected_week = last_30.value / 4.0
            if expected_week <= 0:
                continue
            ratio = last_7.value / expected_week
            if ratio < self.spike_ratio:
                continue
            insight_type = "spike"
            severity = 90
            title = f"Spike reciente en {base_name}"
            summary = f"Ultimos 7d vs 30d: ratio {ratio:.2f}."
            impact_pct = min(max((ratio - 1.0) * self.impact_k, 0.0), self.impact_cap)
            impact_min = impact_pct * 0.7
            impact_max = impact_pct * 1.3
            dedupe_key = f"{base_name}:spike"
            stable_key = f"{project_id}|project|{project_id}|{base_name}|spike"
            insights.append(
                Insight(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key)),
                    project_id=project_id,
                    entity_type="project",
                    entity_id=project_id,
                    type=insight_type,
                    severity=severity,
                    priority=severity,
                    title=title,
                    summary=summary,
                    evidence={
                        "feature": base_name,
                        "last_7d": last_7.value,
                        "last_30d": last_30.value,
                        "ratio": ratio,
                    },
                    explanations={"rule": "spike_ratio"},
                    action={
                        "action_type": "checklist",
                        "action_params": {"feature": base_name},
                        "suggested_due_date": (now + timedelta(days=3)).date().isoformat(),
                        "cta_label": "Revisar cambios",
                    },
                    model_version=self.model_version,
                    features_version=self.features_version,
                    computed_at=now,
                    valid_until=now + timedelta(days=7),
                    status="new",
                    impact_min=impact_min,
                    impact_max=impact_max,
                    impact_unit="%",
                    confidence="medium",
                    dedupe_key=dedupe_key,
                    cooldown_until=cooldown_until,
                    rules_version="v2",
                )
            )

        return insights
