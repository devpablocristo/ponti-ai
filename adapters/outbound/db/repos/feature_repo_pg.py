from adapters.outbound.sql.catalog import list_feature_entries
from adapters.outbound.sql.executor import SQLExecutor
from application.insights.ports.feature_repository import FeatureRepositoryPort, FeatureValue
from app.config import Settings


class FeatureRepositoryPG(FeatureRepositoryPort):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = SQLExecutor(settings)

    def fetch_features(self, project_id: str) -> list[FeatureValue]:
        features: list[FeatureValue] = []
        for entry in list_feature_entries():
            params = entry.validate_params({"project_id": project_id})
            rows = self.executor.execute(
                sql_template=entry.sql_template,
                params=params,
                statement_timeout_ms=self.settings.statement_timeout_ms,
                max_limit=self.settings.max_limit,
                default_limit=self.settings.default_limit,
            )
            for row in rows:
                window = "all"
                if entry.query_id.endswith("_last_30d"):
                    window = "last_30d"
                elif entry.query_id.endswith("_last_7d"):
                    window = "last_7d"
                features.append(
                    FeatureValue(
                        project_id=row.get("project_id", project_id),
                        entity_type=row.get("entity_type", "project"),
                        entity_id=row.get("entity_id", project_id),
                        feature_name=row.get("feature_name", entry.query_id),
                        window=window,
                        value=float(row.get("value", 0.0)),
                    )
                )
        return features
