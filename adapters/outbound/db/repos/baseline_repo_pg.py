import uuid
from datetime import datetime, timezone

from adapters.outbound.db.session import DBSession
from app.config import Settings
from contexts.insights.application.ports.baseline_repository import BaselineRecord, BaselineRepositoryPort


def _stable_id(record: BaselineRecord) -> str:
    scope_id = record.scope_id or ""
    key = f"{record.scope_type}|{scope_id}|{record.cohort_key}|{record.feature_name}|{record.window}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


class BaselineRepositoryPG(BaselineRepositoryPort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def upsert_many(self, records: list[BaselineRecord]) -> int:
        if not records:
            return 0
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                for record in records:
                    cur.execute(
                        """
                        INSERT INTO ai_baselines (
                            id, scope_type, scope_id, cohort_key, feature_name, window_name,
                            p50, p75, p90, n_samples, computed_at
                        ) VALUES (
                            %(id)s, %(scope_type)s, %(scope_id)s, %(cohort_key)s, %(feature_name)s, %(window_name)s,
                            %(p50)s, %(p75)s, %(p90)s, %(n_samples)s, %(computed_at)s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            p50 = EXCLUDED.p50,
                            p75 = EXCLUDED.p75,
                            p90 = EXCLUDED.p90,
                            n_samples = EXCLUDED.n_samples,
                            computed_at = EXCLUDED.computed_at
                        """,
                        {
                            "id": _stable_id(record),
                            "scope_type": record.scope_type,
                            "scope_id": record.scope_id,
                            "cohort_key": record.cohort_key,
                            "feature_name": record.feature_name,
                            "window_name": record.window,
                            "p50": record.p50,
                            "p75": record.p75,
                            "p90": record.p90,
                            "n_samples": record.n_samples,
                            "computed_at": record.computed_at or datetime.now(timezone.utc),
                        },
                    )
            conn.commit()
        return len(records)

    def get_baseline(
        self,
        scope_type: str,
        scope_id: str | None,
        cohort_key: str,
        feature_name: str,
        window: str,
    ) -> BaselineRecord | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ai_baselines
                    WHERE scope_type = %(scope_type)s
                      AND scope_id IS NOT DISTINCT FROM %(scope_id)s
                      AND cohort_key = %(cohort_key)s
                      AND feature_name = %(feature_name)s
                      AND window_name = %(window_name)s
                    ORDER BY computed_at DESC
                    LIMIT 1
                    """,
                    {
                        "scope_type": scope_type,
                        "scope_id": scope_id,
                        "cohort_key": cohort_key,
                        "feature_name": feature_name,
                        "window_name": window,
                    },
                )
                row = cur.fetchone()
        if not row:
            return None
        return BaselineRecord(
            scope_type=row["scope_type"],
            scope_id=row["scope_id"],
            cohort_key=row["cohort_key"],
            feature_name=row["feature_name"],
            window=row["window_name"],
            p50=float(row["p50"]),
            p75=float(row["p75"]),
            p90=float(row["p90"]),
            n_samples=int(row["n_samples"]),
            computed_at=row["computed_at"],
        )
