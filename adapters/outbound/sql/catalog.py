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
        description="Resumen basico del proyecto (costos directos ejecutados).",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "costos_directos_ejecutados_usd::float AS cost_total_usd "
            "FROM v4_report.dashboard_management_balance "
            "WHERE project_id = %(project_id)s::bigint "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "cost_per_ha": SQLCatalogEntry(
        query_id="cost_per_ha",
        description="Costo directo por hectarea del proyecto.",
        sql_template=(
            "SELECT %(project_id)s::text AS project_id, "
            "COALESCE(SUM(direct_cost_total_usd), 0) "
            "/ NULLIF(SUM(hectares), 0)::float AS cost_per_ha_usd "
            "FROM v4_report.lot_metrics "
            "WHERE project_id = %(project_id)s::bigint "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "inputs_by_category": SQLCatalogEntry(
        query_id="inputs_by_category",
        description="Insumos por categoria (USD) del proyecto.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "COALESCE(SUM(semillas_total_usd), 0)::float AS semillas_total_usd, "
            "COALESCE(SUM(curasemillas_total_usd), 0)::float AS curasemillas_total_usd, "
            "COALESCE(SUM(herbicidas_total_usd), 0)::float AS herbicidas_total_usd, "
            "COALESCE(SUM(insecticidas_total_usd), 0)::float AS insecticidas_total_usd, "
            "COALESCE(SUM(fungicidas_total_usd), 0)::float AS fungicidas_total_usd, "
            "COALESCE(SUM(coadyuvantes_total_usd), 0)::float AS coadyuvantes_total_usd, "
            "COALESCE(SUM(fertilizantes_total_usd), 0)::float AS fertilizantes_total_usd, "
            "COALESCE(SUM(otros_insumos_total_usd), 0)::float AS otros_insumos_total_usd, "
            "COALESCE(SUM(total_insumos_usd), 0)::float AS total_insumos_usd "
            "FROM v4_report.field_crop_insumos "
            "WHERE project_id = %(project_id)s::bigint "
            "GROUP BY project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "inputs_total_used": SQLCatalogEntry(
        query_id="inputs_total_used",
        description="Uso total de insumos (USD) del proyecto.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "project_id::text AS entity_id, "
            "COALESCE(SUM(total_insumos_usd), 0)::float AS inputs_total_used "
            "FROM v4_report.field_crop_insumos "
            "WHERE project_id = %(project_id)s::bigint "
            "GROUP BY project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "workorders_count": SQLCatalogEntry(
        query_id="workorders_count",
        description="Cantidad total de ordenes de trabajo del proyecto.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "COALESCE(SUM(total_workorders), 0)::float AS workorders_count "
            "FROM v4_report.labor_metrics "
            "WHERE project_id = %(project_id)s::bigint "
            "GROUP BY project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "workorders_last_30d": SQLCatalogEntry(
        query_id="workorders_last_30d",
        description="Ordenes de trabajo de los ultimos 30 dias.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "COUNT(*)::float AS workorders_count "
            "FROM public.workorders "
            "WHERE project_id = %(project_id)s::bigint "
            "  AND deleted_at IS NULL "
            "  AND date >= (CURRENT_DATE - INTERVAL '30 days') "
            "GROUP BY project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "stock_variance": SQLCatalogEntry(
        query_id="stock_variance",
        description="Diferencia de stock real vs inicial.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "COALESCE(SUM(real_stock_units - initial_units), 0)::float AS stock_variance_units "
            "FROM public.stocks "
            "WHERE project_id = %(project_id)s::bigint "
            "  AND deleted_at IS NULL "
            "GROUP BY project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "total_hectares": SQLCatalogEntry(
        query_id="total_hectares",
        description="Hectareas totales del proyecto.",
        sql_template=(
            "SELECT %(project_id)s::bigint AS project_id, "
            "v4_ssot.total_hectares_for_project(%(project_id)s)::float AS total_hectares "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "total_hectares_by_lot": SQLCatalogEntry(
        query_id="total_hectares_by_lot",
        description="Hectareas por lote del proyecto.",
        sql_template=(
            "SELECT f.project_id::text AS project_id, "
            "l.id::text AS lot_id, "
            "l.hectares::float AS hectares "
            "FROM public.lots l "
            "JOIN public.fields f ON f.id = l.field_id AND f.deleted_at IS NULL "
            "WHERE f.project_id = %(project_id)s::bigint "
            "  AND l.deleted_at IS NULL "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
    "operational_indicators": SQLCatalogEntry(
        query_id="operational_indicators",
        description="Indicadores operativos de la campana activa.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "start_date, "
            "end_date, "
            "campaign_closing_date, "
            "first_workorder_id, "
            "last_workorder_id, "
            "last_stock_count_date "
            "FROM v4_report.dashboard_operational_indicators "
            "WHERE project_id = %(project_id)s::bigint "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=50,
        max_limit=200,
        implemented=True,
    ),
}

_FEATURE_CATALOG: dict[str, SQLCatalogEntry] = {
    "feature_cost_total": SQLCatalogEntry(
        query_id="feature_cost_total",
        description="Costos directos ejecutados por proyecto.",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "project_id::text AS entity_id, "
            "'cost_total'::text AS feature_name, "
            "COALESCE(costos_directos_ejecutados_usd, 0)::float AS value "
            "FROM v4_report.dashboard_management_balance "
            "WHERE project_id = %(project_id)s::bigint "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_cost_per_ha": SQLCatalogEntry(
        query_id="feature_cost_per_ha",
        description="Costo directo por hectarea (proyecto).",
        sql_template=(
            "SELECT %(project_id)s::text AS project_id, "
            "'project'::text AS entity_type, "
            "%(project_id)s::text AS entity_id, "
            "'cost_per_ha'::text AS feature_name, "
            "COALESCE(SUM(direct_cost_total_usd), 0) / NULLIF(SUM(hectares), 0)::float AS value "
            "FROM v4_report.lot_metrics "
            "WHERE project_id = %(project_id)s::bigint "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_inputs_usage": SQLCatalogEntry(
        query_id="feature_inputs_usage",
        description="Uso total de insumos (USD, por proyecto).",
        sql_template=(
            "SELECT project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "project_id::text AS entity_id, "
            "'inputs_total_used'::text AS feature_name, "
            "COALESCE(SUM(total_insumos_usd), 0)::float AS value "
            "FROM v4_report.field_crop_insumos "
            "WHERE project_id = %(project_id)s::bigint "
            "GROUP BY project_id "
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
            "SELECT project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "project_id::text AS entity_id, "
            "'workorders_count'::text AS feature_name, "
            "COALESCE(SUM(total_workorders), 0)::float AS value "
            "FROM v4_report.labor_metrics "
            "WHERE project_id = %(project_id)s::bigint "
            "GROUP BY project_id "
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
            "WHERE s.project_id = %(project_id)s::bigint "
            "  AND s.deleted_at IS NULL "
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
            "SELECT %(project_id)s::text AS project_id, "
            "'project'::text AS entity_type, "
            "%(project_id)s::text AS entity_id, "
            "'total_hectares'::text AS feature_name, "
            "v4_ssot.total_hectares_for_project(%(project_id)s::bigint)::float AS value "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_cost_total_last_30d": SQLCatalogEntry(
        query_id="feature_cost_total_last_30d",
        description="Costos directos ejecutados ultimos 30 dias.",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'cost_total'::text AS feature_name, "
            "COALESCE(SUM(lb.price * w.effective_area), 0)::float AS value "
            "FROM public.workorders w "
            "JOIN public.labors lb ON lb.id = w.labor_id AND lb.deleted_at IS NULL "
            "WHERE w.project_id = %(project_id)s::bigint "
            "  AND w.deleted_at IS NULL "
            "  AND w.effective_area > 0 "
            "  AND w.date >= (CURRENT_DATE - INTERVAL '30 days') "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_cost_total_last_7d": SQLCatalogEntry(
        query_id="feature_cost_total_last_7d",
        description="Costos directos ejecutados ultimos 7 dias.",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'cost_total'::text AS feature_name, "
            "COALESCE(SUM(lb.price * w.effective_area), 0)::float AS value "
            "FROM public.workorders w "
            "JOIN public.labors lb ON lb.id = w.labor_id AND lb.deleted_at IS NULL "
            "WHERE w.project_id = %(project_id)s::bigint "
            "  AND w.deleted_at IS NULL "
            "  AND w.effective_area > 0 "
            "  AND w.date >= (CURRENT_DATE - INTERVAL '7 days') "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_inputs_last_30d": SQLCatalogEntry(
        query_id="feature_inputs_last_30d",
        description="Uso de insumos ultimos 30 dias (total_used).",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'inputs_total_used'::text AS feature_name, "
            "COALESCE(SUM(wi.total_used), 0)::float AS value "
            "FROM public.workorders w "
            "JOIN public.workorder_items wi ON wi.workorder_id = w.id AND wi.deleted_at IS NULL "
            "WHERE w.project_id = %(project_id)s::bigint "
            "  AND w.deleted_at IS NULL "
            "  AND w.date >= (CURRENT_DATE - INTERVAL '30 days') "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_inputs_last_7d": SQLCatalogEntry(
        query_id="feature_inputs_last_7d",
        description="Uso de insumos ultimos 7 dias (total_used).",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'inputs_total_used'::text AS feature_name, "
            "COALESCE(SUM(wi.total_used), 0)::float AS value "
            "FROM public.workorders w "
            "JOIN public.workorder_items wi ON wi.workorder_id = w.id AND wi.deleted_at IS NULL "
            "WHERE w.project_id = %(project_id)s::bigint "
            "  AND w.deleted_at IS NULL "
            "  AND w.date >= (CURRENT_DATE - INTERVAL '7 days') "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_workorders_last_30d": SQLCatalogEntry(
        query_id="feature_workorders_last_30d",
        description="Cantidad de workorders ultimos 30 dias.",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'workorders_count'::text AS feature_name, "
            "COUNT(*)::float AS value "
            "FROM public.workorders w "
            "WHERE w.project_id = %(project_id)s::bigint "
            "  AND w.deleted_at IS NULL "
            "  AND w.date >= (CURRENT_DATE - INTERVAL '30 days') "
            "GROUP BY w.project_id "
            "LIMIT %(limit)s"
        ),
        params_model=ProjectScopeParams,
        default_limit=1,
        max_limit=50,
        implemented=True,
    ),
    "feature_workorders_last_7d": SQLCatalogEntry(
        query_id="feature_workorders_last_7d",
        description="Cantidad de workorders ultimos 7 dias.",
        sql_template=(
            "SELECT w.project_id::text AS project_id, "
            "'project'::text AS entity_type, "
            "w.project_id::text AS entity_id, "
            "'workorders_count'::text AS feature_name, "
            "COUNT(*)::float AS value "
            "FROM public.workorders w "
            "WHERE w.project_id = %(project_id)s::bigint "
            "  AND w.deleted_at IS NULL "
            "  AND w.date >= (CURRENT_DATE - INTERVAL '7 days') "
            "GROUP BY w.project_id "
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
