from typing import Any

from adapters.outbound.db.session import DBSession
from adapters.outbound.sql.validators import validate_sql_template
from app.config import Settings


def _apply_limit(params: dict[str, Any], default_limit: int, max_limit: int) -> dict[str, Any]:
    limit = params.get("limit", default_limit)
    if limit is None:
        limit = default_limit
    if limit > max_limit:
        limit = max_limit
    if limit <= 0:
        limit = default_limit
    params["limit"] = limit
    return params


class SQLExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = DBSession(settings)

    def execute(
        self,
        sql_template: str,
        params: dict[str, Any],
        statement_timeout_ms: int,
        max_limit: int,
        default_limit: int,
    ) -> list[dict[str, Any]]:
        params = _apply_limit(params, default_limit, max_limit)
        sql = validate_sql_template(sql_template)

        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = %s", (statement_timeout_ms,))
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
