from adapters.outbound.sql.catalog import SQLCatalogEntry, get_copilot_entry


class SQLCatalogAdapter:
    def get_entry(self, query_id: str) -> SQLCatalogEntry:
        return get_copilot_entry(query_id)
