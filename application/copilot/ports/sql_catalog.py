from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class SQLCatalogEntry:
    query_id: str
    description: str
    sql_template: str
    default_limit: int
    max_limit: int
    implemented: bool

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        ...


class SQLCatalogPort(Protocol):
    def get_entry(self, query_id: str) -> SQLCatalogEntry:
        ...
