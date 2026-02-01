import uuid
from datetime import datetime, timedelta, timezone

from application.insights.ports.feature_repository import FeatureValue
from domain.insights.entities import Insight


class AnomalyRunner:
    def __init__(
        self,
        model_version: str = "baseline-v1",
        features_version: str = "features-v1",
        ratio_high: float = None,
        ratio_medium: float = None,
    ) -> None:
        self.model_version = model_version
        self.features_version = features_version
        if ratio_high is None or ratio_medium is None:
            raise ValueError("ratios de insights son requeridos")
        self.ratio_high = ratio_high
        self.ratio_medium = ratio_medium

    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        now = datetime.now(timezone.utc)
        insights: list[Insight] = []

        baselines = {
            f.feature_name: f.value
            for f in features
            if f.entity_type == "baseline" and f.entity_id == "all"
        }

        for feature in features:
            if feature.entity_type != "project":
                continue
            baseline = baselines.get(feature.feature_name)
            if baseline is None or baseline == 0:
                continue

            delta_ratio = abs(feature.value - baseline) / abs(baseline)
            if delta_ratio < self.ratio_medium:
                continue

            insight_type = "anomaly" if delta_ratio >= self.ratio_high else "recommendation"
            severity = 80 if insight_type == "anomaly" else 40
            title = f"{feature.feature_name} desvio vs promedio"
            summary = (
                f"Valor {feature.value} vs baseline {baseline} "
                f"({delta_ratio:.2%} de desvio)."
            )

            stable_key = f"{project_id}|{feature.entity_type}|{feature.entity_id}|{feature.feature_name}|{insight_type}"
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
                        "value": feature.value,
                        "baseline": baseline,
                        "delta_ratio": delta_ratio,
                    },
                    explanations={"rule": "baseline_ratio"},
                    action={"suggestion": "Revisar comparativo vs promedio"},
                    model_version=self.model_version,
                    features_version=self.features_version,
                    computed_at=now,
                    valid_until=now + timedelta(days=7),
                    status="new",
                )
            )

        return insights
