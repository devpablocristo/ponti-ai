import re


def validate_sql_template(sql_template: str) -> str:
    sql = sql_template.strip()
    if not sql.lower().startswith("select"):
        raise ValueError("Solo se permite SELECT")
    if ";" in sql:
        raise ValueError("No se permiten multiples statements")
    if "%(project_id)s" not in sql:
        raise ValueError("project_id es obligatorio en el SQL")
    if not re.search(r"\blimit\b", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT %(limit)s"
    return sql
