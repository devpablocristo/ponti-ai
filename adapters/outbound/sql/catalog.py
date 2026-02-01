from dataclasses import dataclass
from typing import Any, Type

from pydantic import BaseModel, Field


class ProjectScopeParams(BaseModel):
    project_id: str = Field(..., min_length=1)
    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class SQLCatalogEntry:
    query_id: str
    description: str
    sql_template: str
    params_model: Type[BaseModel]
    default_limit: int
    max_limit: int
    implemented: bool

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        model = self.params_model(**params)
        values = model.model_dump()
        if values.get("limit") is None:
            values["limit"] = self.default_limit
        return values


_COPILOT_CATALOG: dict[str, SQLCatalogEntry] = {
    "project_overview": SQLCatalogEntry(
        query_id="project_overview",
        description="Resumen general del proyecto (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "lot_costs_summary": SQLCatalogEntry(
        query_id="lot_costs_summary",
        description="Costos por lote (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "labor_costs_summary": SQLCatalogEntry(
        query_id="labor_costs_summary",
        description="Costos de labores (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "inputs_usage_summary": SQLCatalogEntry(
        query_id="inputs_usage_summary",
        description="Uso de insumos (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "yield_trend": SQLCatalogEntry(
        query_id="yield_trend",
        description="Tendencia de rendimiento (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "work_orders_by_status": SQLCatalogEntry(
        query_id="work_orders_by_status",
        description="Ordenes de trabajo por estado (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "invoices_summary": SQLCatalogEntry(
        query_id="invoices_summary",
        description="Resumen de facturas (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
    "anomalies_simple": SQLCatalogEntry(
        query_id="anomalies_simple",
        description="Anomalias basicas (placeholder).",
        sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=False,
    ),
}

_FEATURE_CATALOG: dict[str, SQLCatalogEntry] = {
    "feature_cost_total": SQLCatalogEntry(
        query_id="feature_cost_total",
        description="Costo total estimado por proyecto (labores).",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'cost_total'::text AS feature_name, "
            "COALESCE(SUM(l.price), 0)::float AS value "
            "FROM public.workorders w "
            "JOIN public.labors l ON l.id = w.labor_id "
            "WHERE w.project_id = %(project_id)s "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_cost_per_ha": SQLCatalogEntry(
        query_id="feature_cost_per_ha",
        description="Costo estimado por hectarea (labores / hectareas).",
        sql_template=(
            "WITH total_cost AS ("
            "  SELECT w.project_id, COALESCE(SUM(l.price), 0) AS cost "
            "  FROM public.workorders w "
            "  JOIN public.labors l ON l.id = w.labor_id "
            "  WHERE w.project_id = %(project_id)s "
            "  GROUP BY w.project_id"
            "), total_ha AS ("
            "  SELECT f.project_id, COALESCE(SUM(lo.hectares), 0) AS hectares "
            "  FROM public.fields f "
            "  JOIN public.lots lo ON lo.field_id = f.id "
            "  WHERE f.project_id = %(project_id)s "
            "  GROUP BY f.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'project'::text AS entity_type, "
            "%(project_id)s::text AS entity_id, "
            "'cost_per_ha'::text AS feature_name, "
            "COALESCE(tc.cost / NULLIF(th.hectares, 0), 0)::float AS value "
            "FROM total_cost tc "
            "JOIN total_ha th ON th.project_id = tc.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_inputs_usage": SQLCatalogEntry(
        query_id="feature_inputs_usage",
        description="Uso total de insumos (workorder_items.total_used).",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'inputs_total_used'::text AS feature_name, "
            "COALESCE(SUM(i.total_used), 0)::float AS value "
            "FROM public.workorders w "
            "JOIN public.workorder_items i ON i.workorder_id = w.id "
            "WHERE w.project_id = %(project_id)s "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_workorders_count": SQLCatalogEntry(
        query_id="feature_workorders_count",
        description="Cantidad de ordenes de trabajo por proyecto.",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'workorders_count'::text AS feature_name, "
            "COUNT(*)::float AS value "
            "FROM public.workorders w "
            "WHERE w.project_id = %(project_id)s "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_stock_variance": SQLCatalogEntry(
        query_id="feature_stock_variance",
        description="Diferencia stock real vs inicial (sum).",
        sql_template=(
            "SELECT s.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "s.project_id::text AS entity_id, "
            "'stock_variance'::text AS feature_name, "
            "COALESCE(SUM(s.real_stock_units - s.initial_units), 0)::float AS value "
            "FROM public.stocks s "
            "WHERE s.project_id = %(project_id)s "
            "GROUP BY s.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_total_hectares": SQLCatalogEntry(
        query_id="feature_total_hectares",
        description="Hectareas totales por proyecto.",
        sql_template=(
            "SELECT f.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "f.project_id::text AS entity_id, "
            "'total_hectares'::text AS feature_name, "
            "COALESCE(SUM(lo.hectares), 0)::float AS value "
            "FROM public.fields f "
            "JOIN public.lots lo ON lo.field_id = f.id "
            "WHERE f.project_id = %(project_id)s "
            "GROUP BY f.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "baseline_cost_total": SQLCatalogEntry(
        query_id="baseline_cost_total",
        description="Baseline costo total estimado (promedio entre proyectos).",
        sql_template=(
            "WITH per_project AS ("
            "  SELECT w.project_id, COALESCE(SUM(l.price), 0) AS value "
            "  FROM public.workorders w "
            "  JOIN public.labors l ON l.id = w.labor_id "
            "  GROUP BY w.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'baseline'::text AS entity_type, "
            "'all'::text AS entity_id, "
            "'cost_total'::text AS feature_name, "
            "COALESCE(AVG(value), 0)::float AS value "
            "FROM per_project "
            "WHERE %(project_id)s IS NOT NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=1,
        implemented=True,
    ),
    "baseline_cost_per_ha": SQLCatalogEntry(
        query_id="baseline_cost_per_ha",
        description="Baseline costo por hectarea (promedio entre proyectos).",
        sql_template=(
            "WITH total_cost AS ("
            "  SELECT w.project_id, COALESCE(SUM(l.price), 0) AS cost "
            "  FROM public.workorders w "
            "  JOIN public.labors l ON l.id = w.labor_id "
            "  GROUP BY w.project_id"
            "), total_ha AS ("
            "  SELECT f.project_id, COALESCE(SUM(lo.hectares), 0) AS hectares "
            "  FROM public.fields f "
            "  JOIN public.lots lo ON lo.field_id = f.id "
            "  GROUP BY f.project_id"
            "), per_project AS ("
            "  SELECT tc.project_id, COALESCE(tc.cost / NULLIF(th.hectares, 0), 0) AS value "
            "  FROM total_cost tc "
            "  JOIN total_ha th ON th.project_id = tc.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'baseline'::text AS entity_type, "
            "'all'::text AS entity_id, "
            "'cost_per_ha'::text AS feature_name, "
            "COALESCE(AVG(value), 0)::float AS value "
            "FROM per_project "
            "WHERE %(project_id)s IS NOT NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=1,
        implemented=True,
    ),
    "baseline_inputs_usage": SQLCatalogEntry(
        query_id="baseline_inputs_usage",
        description="Baseline uso de insumos (promedio entre proyectos).",
        sql_template=(
            "WITH per_project AS ("
            "  SELECT w.project_id, COALESCE(SUM(i.total_used), 0) AS value "
            "  FROM public.workorders w "
            "  JOIN public.workorder_items i ON i.workorder_id = w.id "
            "  GROUP BY w.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'baseline'::text AS entity_type, "
            "'all'::text AS entity_id, "
            "'inputs_total_used'::text AS feature_name, "
            "COALESCE(AVG(value), 0)::float AS value "
            "FROM per_project "
            "WHERE %(project_id)s IS NOT NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=1,
        implemented=True,
    ),
    "baseline_workorders_count": SQLCatalogEntry(
        query_id="baseline_workorders_count",
        description="Baseline cantidad de ordenes (promedio entre proyectos).",
        sql_template=(
            "WITH per_project AS ("
            "  SELECT w.project_id, COUNT(*) AS value "
            "  FROM public.workorders w "
            "  GROUP BY w.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'baseline'::text AS entity_type, "
            "'all'::text AS entity_id, "
            "'workorders_count'::text AS feature_name, "
            "COALESCE(AVG(value), 0)::float AS value "
            "FROM per_project "
            "WHERE %(project_id)s IS NOT NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=1,
        implemented=True,
    ),
    "baseline_stock_variance": SQLCatalogEntry(
        query_id="baseline_stock_variance",
        description="Baseline variacion de stock (promedio entre proyectos).",
        sql_template=(
            "WITH per_project AS ("
            "  SELECT s.project_id, COALESCE(SUM(s.real_stock_units - s.initial_units), 0) AS value "
            "  FROM public.stocks s "
            "  GROUP BY s.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'baseline'::text AS entity_type, "
            "'all'::text AS entity_id, "
            "'stock_variance'::text AS feature_name, "
            "COALESCE(AVG(value), 0)::float AS value "
            "FROM per_project "
            "WHERE %(project_id)s IS NOT NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=1,
        implemented=True,
    ),
    "baseline_total_hectares": SQLCatalogEntry(
        query_id="baseline_total_hectares",
        description="Baseline hectareas totales (promedio entre proyectos).",
        sql_template=(
            "WITH per_project AS ("
            "  SELECT f.project_id, COALESCE(SUM(lo.hectares), 0) AS value "
            "  FROM public.fields f "
            "  JOIN public.lots lo ON lo.field_id = f.id "
            "  GROUP BY f.project_id"
            ") "
            "SELECT %(project_id)s::text AS project_id, "
            "'baseline'::text AS entity_type, "
            "'all'::text AS entity_id, "
            "'total_hectares'::text AS feature_name, "
            "COALESCE(AVG(value), 0)::float AS value "
            "FROM per_project "
            "WHERE %(project_id)s IS NOT NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=1,
        implemented=True,
    ),
}


def get_copilot_entry(query_id: str) -> SQLCatalogEntry:
    if query_id not in _COPILOT_CATALOG:
        raise KeyError(f"query_id no permitido: {query_id}")
    return _COPILOT_CATALOG[query_id]


def get_feature_entry(query_id: str) -> SQLCatalogEntry:
    if query_id not in _FEATURE_CATALOG:
        raise KeyError(f"feature_id no permitido: {query_id}")
    return _FEATURE_CATALOG[query_id]


def list_feature_entries() -> list[SQLCatalogEntry]:
    return list(_FEATURE_CATALOG.values())
