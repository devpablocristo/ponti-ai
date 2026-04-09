from contexts.chat.application.project_dossier import (
    build_project_operating_context_for_prompt,
    capture_turn_memory,
    sync_dashboard_snapshot,
    sync_insights_snapshot,
    sync_project_from_backend,
)
from contexts.chat.application.run_ponti_chat import _resolve_route


def test_sync_project_from_backend_builds_project_context() -> None:
    dossier: dict[str, object] = {"project": {"id": "42"}}
    payload = {
        "ok": True,
        "data": {
            "name": "Proyecto Norte",
            "customer": {"name": "Agro Norte"},
            "campaign": {"name": "Campaña 24/25"},
            "managers": [{"name": "Pablo"}],
            "investors": [{"name": "Inversor A"}],
            "fields": [
                {
                    "name": "Campo 1",
                    "lots": [
                        {"name": "Lote A", "hectares": "100.5", "current_crop_name": "Soja"},
                        {"name": "Lote B", "hectares": "20", "current_crop_name": "Maíz"},
                    ],
                }
            ],
        },
    }

    sync_project_from_backend(dossier, payload)

    project = dossier["project"]
    assert project["name"] == "Proyecto Norte"
    assert project["customer_name"] == "Agro Norte"
    assert project["campaign_name"] == "Campaña 24/25"
    assert project["surface_hectares"] == 120.5


def test_build_project_context_includes_memory_and_snapshots() -> None:
    dossier: dict[str, object] = {
        "project": {
            "id": "42",
            "name": "Proyecto Norte",
            "customer_name": "Agro Norte",
            "campaign_name": "Campaña 24/25",
            "fields": [{"name": "Campo 1", "lots": []}],
            "managers": ["Pablo"],
            "surface_hectares": 120.5,
        }
    }
    sync_insights_snapshot(
        dossier,
        new_count_total=3,
        new_count_high_severity=1,
        top_titles=["Stock tensionado", "Costo de labores alto"],
    )
    sync_dashboard_snapshot(
        dossier,
        {
            "ok": True,
            "data": {
                "metrics": {
                    "costs": {"executed_usd": "120000", "budget_usd": "150000"},
                    "operating_result": {"result_usd": "45000", "margin_pct": "18"},
                    "sowing": {"total_hectares": "120.5"},
                },
                "management_balance": {"totals": {"stock_usd": "30000"}},
                "operational_indicators": {"items": [{"title": "2 OT atrasadas"}]},
            },
        },
    )
    capture_turn_memory(
        dossier,
        user_id="u-1",
        user_message="Recordá que este proyecto prioriza caja y respuestas breves",
        assistant_reply="Entendido",
        routed_agent="dashboard",
        tool_calls=["fetch_dashboard"],
    )

    context = build_project_operating_context_for_prompt(dossier, "u-1")

    assert "Proyecto actual: Proyecto Norte." in context
    assert "Cliente del proyecto: Agro Norte." in context
    assert "Campaña principal: Campaña 24/25." in context
    assert "Insights activos recientes: 3 total, 1 de alta severidad." in context
    assert "resultado operativo USD: 45000" in context
    assert "El usuario prefiere respuestas breves." in context


def test_executive_requests_override_flat_module_route() -> None:
    routed, source = _resolve_route(
        "supplies",
        "Quiero una mirada de dueño del proyecto con prioridades, riesgos y acciones concretas.",
    )
    assert routed == "dashboard"
    assert source == "orchestrator"


def test_operational_requests_keep_specific_route() -> None:
    routed, source = _resolve_route("", "Necesito revisar labores agrupadas por orden de trabajo")
    assert routed == "labors"
    assert source == "orchestrator"
