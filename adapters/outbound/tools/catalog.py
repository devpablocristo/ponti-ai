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
    for key in required:
        if key not in tool_args:
            return False, f"tool_args missing required: {key}"

    props: dict[str, Any] = schema.get("properties", {}) or {}
    for key, spec in props.items():
        if key not in tool_args:
            continue
        expected = spec.get("type")
        value = tool_args[key]
        if expected == "string" and not isinstance(value, str):
            return False, f"tool_args.{key} debe ser string"
        if expected == "number" and not isinstance(value, (int, float)):
            return False, f"tool_args.{key} debe ser number"
        if expected == "integer" and not isinstance(value, int):
            return False, f"tool_args.{key} debe ser integer"
        if expected == "object" and not isinstance(value, dict):
            return False, f"tool_args.{key} debe ser object"
        if expected == "array" and not isinstance(value, list):
            return False, f"tool_args.{key} debe ser array"

    return True, None

