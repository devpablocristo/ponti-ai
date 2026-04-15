"""Tools de lectura del asistente: ponti-backend + resumen de insights local."""

from __future__ import annotations

import asyncio
from typing import Any

from runtime.domain.models import ToolDeclaration

from src.tools.ponti_backend import PontiBackendClient
from src.insights.service import GetSummary

_API = "/api/v1"


def _i(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _workspace_params(
    project_id: str,
    *,
    customer_id: Any = None,
    campaign_id: Any = None,
    field_id: Any = None,
) -> dict[str, Any]:
    p: dict[str, Any] = {"project_id": project_id}
    c, ca, f = _i(customer_id), _i(campaign_id), _i(field_id)
    if c is not None:
        p["customer_id"] = c
    if ca is not None:
        p["campaign_id"] = ca
    if f is not None:
        p["field_id"] = f
    return p


def build_ponti_tool_declarations(*, backend_configured: bool) -> list[ToolDeclaration]:
    """Declaraciones JSON-schema para el LLM (solo lectura)."""
    decls: list[ToolDeclaration] = [
        ToolDeclaration(
            name="get_insights_summary",
            description=(
                "Resumen de insights del proyecto en ponti-ai: totales y top títulos. "
                "Usar para alertas, salud del proyecto y priorización."
            ),
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
        ),
    ]

    if not backend_configured:
        return decls

    common_workspace = {
        "customer_id": {"type": "integer", "description": "Filtro opcional cliente."},
        "campaign_id": {"type": "integer", "description": "Filtro opcional campaña."},
        "field_id": {"type": "integer", "description": "Filtro opcional campo."},
    }

    decls.extend(
        [
            ToolDeclaration(
                name="fetch_dashboard",
                description="Datos agregados del tablero (dashboard) para el workspace actual.",
                parameters={
                    "type": "object",
                    "properties": dict(common_workspace),
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_labors_catalog",
                description="Listado paginado de labores del catálogo del proyecto (no agrupadas por OT).",
                parameters={
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "description": "Página (default 1)."},
                        "per_page": {"type": "integer", "description": "Tamaño (default 50, máx 100)."},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_labors_grouped",
                description="Labores agrupadas por orden de trabajo; útil para costos por OT.",
                parameters={
                    "type": "object",
                    "properties": {
                        **common_workspace,
                        "field_id": {"type": "integer", "description": "Opcional: filtrar por campo."},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_labor_metrics",
                description="Métricas globales de labores (workspace opcional vía filtros).",
                parameters={
                    "type": "object",
                    "properties": dict(common_workspace),
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_supplies",
                description="Listado paginado de insumos del proyecto/workspace.",
                parameters={
                    "type": "object",
                    "properties": {
                        **common_workspace,
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "mode": {"type": "string", "description": "Modo de listado si aplica (string vacío = default)."},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_supply_detail",
                description="Detalle de un insumo por ID.",
                parameters={
                    "type": "object",
                    "properties": {"supply_id": {"type": "integer"}},
                    "required": ["supply_id"],
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_lots",
                description="Listado paginado de lotes con filtros de workspace.",
                parameters={
                    "type": "object",
                    "properties": {
                        **common_workspace,
                        "crop_id": {"type": "integer"},
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_lot_detail",
                description="Detalle de un lote por ID.",
                parameters={
                    "type": "object",
                    "properties": {"lot_id": {"type": "integer"}},
                    "required": ["lot_id"],
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_lot_metrics",
                description="Métricas de lotes (project_id/field_id/crop_id opcionales).",
                parameters={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "integer", "description": "Override opcional; por defecto usa el proyecto del chat."},
                        "field_id": {"type": "integer"},
                        "crop_id": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_campaigns",
                description="Campañas; puede filtrar por cliente y nombre de proyecto.",
                parameters={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "integer"},
                        "project_name": {"type": "string", "description": "Filtro por nombre de proyecto (parcial)."},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_work_orders",
                description="Listado paginado de órdenes de trabajo.",
                parameters={
                    "type": "object",
                    "properties": {**common_workspace},
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_work_order_detail",
                description="Detalle de una orden de trabajo por ID.",
                parameters={
                    "type": "object",
                    "properties": {"work_order_id": {"type": "integer"}},
                    "required": ["work_order_id"],
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_work_order_metrics",
                description="Métricas de órdenes de trabajo para el workspace.",
                parameters={
                    "type": "object",
                    "properties": dict(common_workspace),
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_stock_summary",
                description="Resumen de stock del proyecto; cutoff_date opcional YYYY-MM-DD.",
                parameters={
                    "type": "object",
                    "properties": {"cutoff_date": {"type": "string", "description": "Fecha tope opcional."}},
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_stock_periods",
                description="Periodos de stock disponibles para el proyecto.",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            ToolDeclaration(
                name="fetch_supply_movements",
                description="Movimientos de insumos del proyecto (listado completo expuesto por backend; puede truncarse).",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            ToolDeclaration(
                name="fetch_customers",
                description="Clientes activos/archivados (paginado).",
                parameters={
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "status": {
                            "type": "string",
                            "description": "active | archived | all (default active).",
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_customer_detail",
                description="Detalle de cliente por ID.",
                parameters={
                    "type": "object",
                    "properties": {"customer_id": {"type": "integer"}},
                    "required": ["customer_id"],
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_project_detail",
                description="Detalle del proyecto actual por ID de path (debe coincidir con el del chat).",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            ToolDeclaration(
                name="fetch_projects_list",
                description="Listado de proyectos (paginado).",
                parameters={
                    "type": "object",
                    "properties": {"page": {"type": "integer"}, "per_page": {"type": "integer"}},
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_data_integrity_costs",
                description="Chequeo de coherencia de costos directos (integridad de datos).",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            ToolDeclaration(
                name="fetch_report_field_crop",
                description="Informe por campo/cultivo.",
                parameters={
                    "type": "object",
                    "properties": dict(common_workspace),
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_report_investor_contribution",
                description="Informe de aportes por inversor.",
                parameters={
                    "type": "object",
                    "properties": dict(common_workspace),
                    "additionalProperties": False,
                },
            ),
            ToolDeclaration(
                name="fetch_report_summary_results",
                description="Resumen de resultados (summary-results).",
                parameters={
                    "type": "object",
                    "properties": dict(common_workspace),
                    "additionalProperties": False,
                },
            ),
        ]
    )
    return decls


def build_ponti_tool_handlers(
    *,
    get_summary: GetSummary,
    backend: PontiBackendClient | None,
) -> dict[str, Any]:
    """Handlers async compatibles con runtime.orchestrator (kwargs = context + tool args)."""

    async def get_insights_summary(project_id: str, **_kw: Any) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            summary = get_summary.handle(project_id)
            tops = [
                {"id": i.id, "title": i.title, "severity": i.severity, "type": i.type}
                for i in summary.top_insights[:12]
            ]
            return {
                "ok": True,
                "new_count_total": summary.new_count_total,
                "new_count_high_severity": summary.new_count_high_severity,
                "top_insights": tops,
            }

        return await asyncio.to_thread(_run)

    handlers: dict[str, Any] = {"get_insights_summary": get_insights_summary}

    if backend is None or not backend.is_configured():
        return handlers

    async def fetch_dashboard(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/dashboard", user_id=user_id, params=params)

    async def fetch_labors_catalog(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        page = _i(kw.get("page")) or 1
        per = min(100, max(1, _i(kw.get("per_page")) or 50))
        pid = str(project_id).strip()
        return await backend.get_json(
            f"{_API}/projects/{pid}/labors",
            user_id=user_id,
            params={"page": page, "per_page": per},
        )

    async def fetch_labors_grouped(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        pid = str(project_id).strip()
        params: dict[str, Any] = {}
        if kw.get("field_id") is not None:
            params["field_id"] = _i(kw.get("field_id"))
        return await backend.get_json(f"{_API}/labors/group/{pid}", user_id=user_id, params=params or None)

    async def fetch_labor_metrics(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/labors/metrics", user_id=user_id, params=params)

    async def fetch_supplies(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        params["page"] = _i(kw.get("page")) or 1
        params["per_page"] = min(200, max(1, _i(kw.get("per_page")) or 50))
        mode = kw.get("mode")
        if isinstance(mode, str) and mode.strip():
            params["mode"] = mode.strip()
        return await backend.get_json(f"{_API}/supplies", user_id=user_id, params=params)

    async def fetch_supply_detail(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        sid = _i(kw.get("supply_id"))
        if sid is None:
            return {"ok": False, "error": "supply_id_required"}
        return await backend.get_json(f"{_API}/supplies/{sid}", user_id=user_id, params=None)

    async def fetch_lots(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        if kw.get("crop_id") is not None:
            params["crop_id"] = _i(kw.get("crop_id"))
        params["page"] = _i(kw.get("page")) or 1
        params["per_page"] = min(1000, max(1, _i(kw.get("per_page")) or 100))
        return await backend.get_json(f"{_API}/lots", user_id=user_id, params=params)

    async def fetch_lot_detail(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        lid = _i(kw.get("lot_id"))
        if lid is None:
            return {"ok": False, "error": "lot_id_required"}
        return await backend.get_json(f"{_API}/lots/{lid}", user_id=user_id, params=None)

    async def fetch_lot_metrics(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params: dict[str, Any] = {}
        op = _i(kw.get("project_id"))
        params["project_id"] = op if op is not None else int(str(project_id).strip())
        if kw.get("field_id") is not None:
            params["field_id"] = _i(kw.get("field_id"))
        if kw.get("crop_id") is not None:
            params["crop_id"] = _i(kw.get("crop_id"))
        return await backend.get_json(f"{_API}/lots/metrics", user_id=user_id, params=params)

    async def fetch_campaigns(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if kw.get("customer_id") is not None:
            params["customer_id"] = _i(kw.get("customer_id"))
        pn = kw.get("project_name")
        if isinstance(pn, str) and pn.strip():
            params["project_name"] = pn.strip()
        return await backend.get_json(f"{_API}/campaigns", user_id=user_id, params=params or None)

    async def fetch_work_orders(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/work-orders", user_id=user_id, params=params)

    async def fetch_work_order_detail(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        wid = _i(kw.get("work_order_id"))
        if wid is None:
            return {"ok": False, "error": "work_order_id_required"}
        return await backend.get_json(f"{_API}/work-orders/{wid}", user_id=user_id, params=None)

    async def fetch_work_order_metrics(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/work-orders/metrics", user_id=user_id, params=params)

    async def fetch_stock_summary(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        pid = str(project_id).strip()
        params: dict[str, Any] = {}
        cd = kw.get("cutoff_date")
        if isinstance(cd, str) and cd.strip():
            params["cutoff_date"] = cd.strip()
        return await backend.get_json(f"{_API}/projects/{pid}/stocks/summary", user_id=user_id, params=params or None)

    async def fetch_stock_periods(project_id: str, user_id: str, **_kw: Any) -> dict[str, Any]:
        pid = str(project_id).strip()
        return await backend.get_json(f"{_API}/projects/{pid}/stocks/periods", user_id=user_id, params=None)

    async def fetch_supply_movements(project_id: str, user_id: str, **_kw: Any) -> dict[str, Any]:
        pid = str(project_id).strip()
        return await backend.get_json(f"{_API}/projects/{pid}/supply-movements", user_id=user_id, params=None)

    async def fetch_customers(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        _ = project_id
        page = _i(kw.get("page")) or 1
        per = min(200, max(1, _i(kw.get("per_page")) or 50))
        st = kw.get("status")
        status = st if isinstance(st, str) and st.strip() else "active"
        return await backend.get_json(
            f"{_API}/customers",
            user_id=user_id,
            params={"page": page, "per_page": per, "status": status},
        )

    async def fetch_customer_detail(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        _ = project_id
        cid = _i(kw.get("customer_id"))
        if cid is None:
            return {"ok": False, "error": "customer_id_required"}
        return await backend.get_json(f"{_API}/customers/{cid}", user_id=user_id, params=None)

    async def fetch_project_detail(project_id: str, user_id: str, **_kw: Any) -> dict[str, Any]:
        pid = str(project_id).strip()
        return await backend.get_json(f"{_API}/projects/{pid}", user_id=user_id, params=None)

    async def fetch_projects_list(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        _ = project_id
        page = _i(kw.get("page")) or 1
        per = min(200, max(1, _i(kw.get("per_page")) or 50))
        return await backend.get_json(f"{_API}/projects", user_id=user_id, params={"page": page, "per_page": per})

    async def fetch_data_integrity_costs(project_id: str, user_id: str, **_kw: Any) -> dict[str, Any]:
        return await backend.get_json(
            f"{_API}/data-integrity/costs-check",
            user_id=user_id,
            params={"project_id": int(str(project_id).strip())},
        )

    async def fetch_report_field_crop(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/reports/field-crop", user_id=user_id, params=params)

    async def fetch_report_investor_contribution(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/reports/investor-contribution", user_id=user_id, params=params)

    async def fetch_report_summary_results(project_id: str, user_id: str, **kw: Any) -> dict[str, Any]:
        params = _workspace_params(project_id, customer_id=kw.get("customer_id"), campaign_id=kw.get("campaign_id"), field_id=kw.get("field_id"))
        return await backend.get_json(f"{_API}/reports/summary-results", user_id=user_id, params=params)

    handlers.update(
        {
            "fetch_dashboard": fetch_dashboard,
            "fetch_labors_catalog": fetch_labors_catalog,
            "fetch_labors_grouped": fetch_labors_grouped,
            "fetch_labor_metrics": fetch_labor_metrics,
            "fetch_supplies": fetch_supplies,
            "fetch_supply_detail": fetch_supply_detail,
            "fetch_lots": fetch_lots,
            "fetch_lot_detail": fetch_lot_detail,
            "fetch_lot_metrics": fetch_lot_metrics,
            "fetch_campaigns": fetch_campaigns,
            "fetch_work_orders": fetch_work_orders,
            "fetch_work_order_detail": fetch_work_order_detail,
            "fetch_work_order_metrics": fetch_work_order_metrics,
            "fetch_stock_summary": fetch_stock_summary,
            "fetch_stock_periods": fetch_stock_periods,
            "fetch_supply_movements": fetch_supply_movements,
            "fetch_customers": fetch_customers,
            "fetch_customer_detail": fetch_customer_detail,
            "fetch_project_detail": fetch_project_detail,
            "fetch_projects_list": fetch_projects_list,
            "fetch_data_integrity_costs": fetch_data_integrity_costs,
            "fetch_report_field_crop": fetch_report_field_crop,
            "fetch_report_investor_contribution": fetch_report_investor_contribution,
            "fetch_report_summary_results": fetch_report_summary_results,
        }
    )

    return handlers
