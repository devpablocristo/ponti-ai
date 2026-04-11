import uuid
from datetime import datetime, timedelta, timezone

from src.insights.repository import BaselineRepositoryPG
from src.insights.domain import FeatureValue
from src.insights.domain import Insight


class AnomalyRunner:
    def __init__(
        self,
        baseline_repo: BaselineRepositoryPG,
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
        cooldown_until = now + timedelta(days=self.cooldown_days)
        cohort_key = self._resolve_cohort_key(features)
        feature_map = self._project_feature_map(features)
        insights: list[Insight] = []

        for feature in self._project_features(features):
            baseline, baseline_scope = self._resolve_baseline(project_id, cohort_key, feature.feature_name, feature.window)
            if baseline is None:
                continue
            classification = self._classify_feature(feature.value, baseline.p75, baseline.p90)
            if classification is None:
                continue
            insight_type, severity, delta_ratio = classification
            insights.append(
                self._build_baseline_insight(
                    project_id=project_id,
                    feature=feature,
                    baseline=baseline,
                    baseline_scope=baseline_scope,
                    cohort_key=cohort_key,
                    insight_type=insight_type,
                    severity=severity,
                    delta_ratio=delta_ratio,
                    now=now,
                    cooldown_until=cooldown_until,
                )
            )

        insights.extend(self._build_spike_insights(project_id, feature_map, now, cooldown_until))
        return insights

    @staticmethod
    def _project_features(features: list[FeatureValue]) -> list[FeatureValue]:
        return [feature for feature in features if feature.entity_type == "project"]

    def _resolve_cohort_key(self, features: list[FeatureValue]) -> str:
        total_hectares = None
        for feature in self._project_features(features):
            if feature.feature_name == "total_hectares" and feature.window == "all":
                total_hectares = feature.value
                break
        if total_hectares is None:
            return "size=unknown"
        if total_hectares <= self.size_small_max:
            return "size=small"
        if total_hectares <= self.size_medium_max:
            return "size=medium"
        return "size=large"

    def _project_feature_map(self, features: list[FeatureValue]) -> dict[tuple[str, str], FeatureValue]:
        return {
            (feature.feature_name, feature.window): feature
            for feature in self._project_features(features)
        }

    def _resolve_baseline(
        self,
        project_id: str,
        cohort_key: str,
        feature_name: str,
        window: str,
    ):
        baseline = self.baseline_repo.get_baseline(
            scope_type="project",
            scope_id=project_id,
            cohort_key="self",
            feature_name=feature_name,
            window=window,
        )
        if baseline is not None:
            return baseline, "project"

        baseline = self.baseline_repo.get_baseline(
            scope_type="global",
            scope_id=None,
            cohort_key=cohort_key,
            feature_name=feature_name,
            window=window,
        )
        if baseline is not None:
            return baseline, "cohort"

        baseline = self.baseline_repo.get_baseline(
            scope_type="global",
            scope_id=None,
            cohort_key=cohort_key,
            feature_name=feature_name,
            window="all",
        )
        return baseline, "cohort"

    @staticmethod
    def _classify_feature(value: float, p75: float, p90: float) -> tuple[str, int, float] | None:
        if value >= p90:
            delta_ratio = (value - p90) / p90 if p90 else 0
            return "anomaly", 80, delta_ratio
        if value >= p75:
            delta_ratio = (value - p75) / p75 if p75 else 0
            return "recommendation", 40, delta_ratio
        return None

    def _impact_bounds(self, delta_ratio: float) -> tuple[float, float]:
        impact_pct = min(max(delta_ratio * self.impact_k, 0.0), self.impact_cap)
        return impact_pct * 0.7, impact_pct * 1.3

    @staticmethod
    def _confidence(n_samples: int) -> str:
        if n_samples >= 50:
            return "high"
        if n_samples >= 20:
            return "medium"
        return "low"

    @staticmethod
    def _action_for_feature(feature_name: str) -> tuple[str, str]:
        if feature_name in ("inputs_total_used", "stock_variance"):
            return "inventory_check", "Revisar stock"
        if feature_name in ("cost_total", "cost_per_ha"):
            return "review_inputs", "Revisar costos"
        return "checklist", "Revisar"

    def _build_baseline_insight(
        self,
        *,
        project_id: str,
        feature: FeatureValue,
        baseline,
        baseline_scope: str,
        cohort_key: str,
        insight_type: str,
        severity: int,
        delta_ratio: float,
        now: datetime,
        cooldown_until: datetime,
    ) -> Insight:
        impact_min, impact_max = self._impact_bounds(delta_ratio)
        action_type, cta_label = self._action_for_feature(feature.feature_name)
        dedupe_key = f"{feature.feature_name}:{feature.window}:{insight_type}"
        stable_key = (
            f"{project_id}|{feature.entity_type}|{feature.entity_id}|"
            f"{feature.feature_name}|{feature.window}|{insight_type}"
        )
        return Insight(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key)),
            project_id=project_id,
            entity_type=feature.entity_type,
            entity_id=feature.entity_id,
            type=insight_type,
            severity=severity,
            priority=severity,
            title=f"{feature.feature_name} alto vs baseline",
            summary=(
                f"Valor {feature.value} vs p75 {baseline.p75} y p90 {baseline.p90} "
                f"({baseline_scope}, {cohort_key})."
            ),
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
            confidence=self._confidence(baseline.n_samples),
            dedupe_key=dedupe_key,
            cooldown_until=cooldown_until,
            rules_version="v2",
        )

    def _build_spike_insights(
        self,
        project_id: str,
        feature_map: dict[tuple[str, str], FeatureValue],
        now: datetime,
        cooldown_until: datetime,
    ) -> list[Insight]:
        insights: list[Insight] = []
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

            impact_min, impact_max = self._impact_bounds(ratio - 1.0)
            dedupe_key = f"{base_name}:spike"
            stable_key = f"{project_id}|project|{project_id}|{base_name}|spike"
            insights.append(
                Insight(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key)),
                    project_id=project_id,
                    entity_type="project",
                    entity_id=project_id,
                    type="spike",
                    severity=90,
                    priority=90,
                    title=f"Spike reciente en {base_name}",
                    summary=f"Ultimos 7d vs 30d: ratio {ratio:.2f}.",
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
