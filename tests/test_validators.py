import pytest

from adapters.outbound.sql.validators import validate_sql_template


def test_validate_select_only() -> None:
    with pytest.raises(ValueError):
        validate_sql_template("UPDATE foo SET a=1")


def test_validate_no_multiple_statements() -> None:
    with pytest.raises(ValueError):
        validate_sql_template("SELECT 1; SELECT 2")


def test_validate_project_id_required() -> None:
    with pytest.raises(ValueError):
        validate_sql_template("SELECT 1 LIMIT %(limit)s")


def test_validate_adds_limit() -> None:
    sql = validate_sql_template("SELECT %(project_id)s::text AS project_id")
    assert "LIMIT %(limit)s" in sql


def test_validate_allows_with_select() -> None:
    sql = validate_sql_template(
        "WITH base AS (SELECT %(project_id)s::text AS project_id) SELECT * FROM base"
    )
    assert "LIMIT %(limit)s" in sql
