import re


def validate_sql_template(sql_template: str) -> str:
    sql = sql_template.strip()
    sql_lower = sql.lower()
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        raise ValueError("Solo se permite SELECT")
    if sql_lower.startswith("with") and not re.search(r"\bselect\b", sql_lower):
        raise ValueError("Solo se permite SELECT")
    if ";" in sql:
        raise ValueError("No se permiten multiples statements")
    if "%(project_id)s" not in sql:
        raise ValueError("project_id es obligatorio en el SQL")
    if not re.search(r"\blimit\b", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT %(limit)s"
    return sql
