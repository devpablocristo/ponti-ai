from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TOOLS_CATALOG_VERSION = "tools_v1"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: dict[str, Any]


_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="request_cost_breakdown",
        description=(
            "Genera una solicitud interna para obtener desglose causal de un costo "
            "(insumos, labores, logística, ajustes) y validar calidad de datos."
        ),
        args_schema={
            "type": "object",
            "additionalProperties": True,
            "required": ["insight_id", "project_id", "feature", "time_window"],
            "properties": {
                "insight_id": {"type": "string"},
                "project_id": {"type": "string"},
                "entity_type": {"type": "string"},
                "entity_id": {"type": "string"},
                "feature": {"type": "string"},
                "time_window": {"type": "string"},
                "current_value": {"type": "number"},
                "baseline_value": {"type": "number"},
                "delta_percentage": {"type": "number"},
                "cohort_key": {"type": "string"},
                "n_samples": {"type": "integer"},
            },
        },
    ),
    ToolSpec(
        name="create_review_task",
        description="Crea una tarea interna de revisión asociada a un insight, con responsable y fecha límite.",
        args_schema={
            "type": "object",
            "additionalProperties": True,
            "required": ["insight_id", "project_id", "title", "due_date"],
            "properties": {
                "insight_id": {"type": "string"},
                "project_id": {"type": "string"},
                "entity_type": {"type": "string"},
                "entity_id": {"type": "string"},
                "title": {"type": "string"},
                "due_date": {"type": "string"},
                "context": {"type": "object"},
                "checklist": {"type": "array"},
            },
        },
    ),
    ToolSpec(
        name="recompute_baselines",
        description="Dispara la recomputación de baselines para un proyecto y/o cohorte.",
        args_schema={
            "type": "object",
            "additionalProperties": True,
            "required": ["project_id"],
            "properties": {
                "project_id": {"type": "string"},
                "cohort_key": {"type": "string"},
                "features": {"type": "array"},
                "time_windows": {"type": "array"},
                "reason": {"type": "string"},
                "priority": {"type": "string"},
            },
        },
    ),
    ToolSpec(
        name="recompute_insights",
        description="Recalcula insights para una entidad luego de cambios en datos o baselines.",
        args_schema={
            "type": "object",
            "additionalProperties": True,
            "required": ["project_id", "entity_type", "entity_id"],
            "properties": {
                "project_id": {"type": "string"},
                "entity_type": {"type": "string"},
                "entity_id": {"type": "string"},
                "reason": {"type": "string"},
                "priority": {"type": "string"},
            },
        },
    ),
]


def list_tools() -> list[ToolSpec]:
    return list(_TOOLS)


def get_tool(name: str) -> ToolSpec | None:
    for tool in _TOOLS:
        if tool.name == name:
            return tool
    return None


def list_tools_as_json() -> list[dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "args_schema": t.args_schema} for t in _TOOLS]


def _validate_required_keys(tool_args: dict[str, Any], required: list[Any]) -> tuple[bool, str | None]:
    for key in required:
        if key not in tool_args:
            return False, f"tool_args missing required: {key}"
    return True, None


def _validate_arg_type(key: str, expected: str | None, value: Any) -> tuple[bool, str | None]:
    validators: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "object": dict,
        "array": list,
    }
    if expected is None or expected not in validators:
        return True, None
    if isinstance(value, validators[expected]):
        return True, None
    return False, f"tool_args.{key} debe ser {expected}"


def _validate_property_types(tool_args: dict[str, Any], props: dict[str, Any]) -> tuple[bool, str | None]:
    for key, spec in props.items():
        if key not in tool_args:
            continue
        ok, error = _validate_arg_type(key, spec.get("type"), tool_args[key])
        if not ok:
            return ok, error
    return True, None


def validate_tool_args(tool_name: str, tool_args: Any) -> tuple[bool, str | None]:
    """
    Valida tool_args contra un subset práctico de JSON Schema (type/required/properties).
    Evitamos dependencias extra (jsonschema) y mantenemos el contrato controlado.
    """
    tool = get_tool(tool_name)
    if tool is None:
        return False, "tool no permitido"

    schema = tool.args_schema
    if schema.get("type") != "object":
        return False, "args_schema inválido (solo object)"
    if not isinstance(tool_args, dict):
        return False, "tool_args debe ser object"

    required = schema.get("required", [])
    ok, error = _validate_required_keys(tool_args, required)
    if not ok:
        return ok, error

    props: dict[str, Any] = schema.get("properties", {}) or {}
    return _validate_property_types(tool_args, props)
