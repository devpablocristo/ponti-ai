import pytest

from adapters.outbound.sql.catalog import get_copilot_entry


def test_catalog_known_query() -> None:
    entry = get_copilot_entry("project_overview")
    params = entry.validate_params({"project_id": "p-1"})
    assert params["project_id"] == "p-1"
    assert "limit" in params


def test_catalog_unknown_query() -> None:
    with pytest.raises(KeyError):
        get_copilot_entry("no-existe")
