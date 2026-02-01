from typing import Any, Protocol


class SQLExecutorPort(Protocol):
    def execute(
        self,
        sql_template: str,
        params: dict[str, Any],
        statement_timeout_ms: int,
        max_limit: int,
        default_limit: int,
    ) -> list[dict[str, Any]]:
        ...
