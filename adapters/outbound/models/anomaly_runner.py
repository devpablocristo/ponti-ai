import uuid
from datetime import datetime, timedelta, timezone

from application.insights.ports.feature_repository import FeatureValue
from domain.insights.entities import Insight


class AnomalyRunner:
    def __init__(self, model_version: str = "baseline-v1", features_version: str = "features-v1") -> None:
        self.model_version = model_version
        self.features_version = features_version

    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        now = datetime.now(timezone.utc)
        insights: list[Insight] = []

        for feature in features:
            severity = min(100, int(abs(feature.value) * 5))
            if severity <= 0:
                continue

            insight_type = "anomaly" if severity >= 50 else "recommendation"
            title = f"{feature.feature_name} fuera de rango"
            summary = f"Valor detectado {feature.value} para {feature.feature_name}."

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
                    evidence={"feature": feature.feature_name, "value": feature.value},
                    explanations={"rule": "baseline"},
                    action={"suggestion": "Revisar valores historicos"},
                    model_version=self.model_version,
                    features_version=self.features_version,
                    computed_at=now,
                    valid_until=now + timedelta(days=7),
                    status="new",
                )
            )

        return insights
