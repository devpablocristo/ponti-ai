from fastapi.testclient import TestClient

from core_ai.completions import LLMRateLimitError
from contexts.copilot.application.use_cases.explain_insight import InsightNotFoundError
from app.main import create_app


def _set_base_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_NAME", "ponti-ai")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DB_DSN", "postgresql://unused")
    monkeypatch.setenv("AI_SERVICE_KEYS", "test-ai-service-key")
    monkeypatch.setenv("STATEMENT_TIMEOUT_MS", "1000")
    monkeypatch.setenv("MAX_LIMIT", "100")
    monkeypatch.setenv("DEFAULT_LIMIT", "50")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("LLM_MODEL", "stub")
    monkeypatch.setenv("INSIGHTS_RATIO_HIGH", "0.5")
    monkeypatch.setenv("INSIGHTS_RATIO_MEDIUM", "0.2")
    monkeypatch.setenv("INSIGHTS_SPIKE_RATIO", "1.5")
    monkeypatch.setenv("INSIGHTS_COOLDOWN_DAYS", "7")
    monkeypatch.setenv("INSIGHTS_IMPACT_K", "1.0")
    monkeypatch.setenv("INSIGHTS_IMPACT_CAP", "2.0")
    monkeypatch.setenv("INSIGHTS_SIZE_SMALL_MAX", "200")
    monkeypatch.setenv("INSIGHTS_SIZE_MEDIUM_MAX", "1000")


def test_copilot_routes_not_mounted_when_disabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "false")

    client = TestClient(create_app())
    assert client.get("/v1/copilot/insights/abc/explain").status_code == 404
    assert client.get("/v1/copilot/insights/abc/why").status_code == 404
    assert client.get("/v1/copilot/insights/abc/next-steps").status_code == 404


def test_copilot_routes_exist_when_enabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")

    client = TestClient(create_app())
    # Sin auth → 401 (la ruta EXISTE pero requiere headers)
    assert client.get("/v1/copilot/insights/abc/explain").status_code == 401
    assert client.get("/v1/copilot/insights/abc/why").status_code == 401
    assert client.get("/v1/copilot/insights/abc/next-steps").status_code == 401


def test_removed_routes_return_404(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")

    client = TestClient(create_app())
    assert client.post("/v1/rag/ingest").status_code == 404
    assert client.get("/v1/ml/status").status_code == 404
    assert client.post("/v1/jobs/recompute-active").status_code == 404
    assert client.get("/v1/admin/anything").status_code == 404
    assert client.post("/v1/queue/process").status_code == 404


def test_health_endpoints_no_auth(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)

    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_insights_endpoints_require_auth(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)

    client = TestClient(create_app())
    assert client.post("/v1/insights/compute").status_code == 401
    assert client.get("/v1/insights/summary").status_code == 401
    assert client.get("/v1/insights/project/1").status_code == 401
    assert client.post("/v1/insights/ins-1/actions", json={"action": "ack", "new_status": "acknowledged"}).status_code == 401


def test_app_version(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)

    client = TestClient(create_app())
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["version"] == "1.0.0-mvp"


def test_openapi_exposes_shared_surface_metadata(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")

    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    schemas = schema["components"]["schemas"]

    assert "request_id" in schemas["ExplainInsightResponse"]["properties"]
    assert "output_kind" in schemas["ExplainInsightResponse"]["properties"]
    assert "routing_source" in schemas["ExplainInsightResponse"]["properties"]
    assert "service_kind" in schemas["ComputeInsightsResponse"]["properties"]
    assert "request_id" in schemas["InsightListResponse"]["properties"]
    assert "output_kind" in schemas["SummaryResponse"]["properties"]
    assert "service_kind" in schemas["ActionResponse"]["properties"]


def test_copilot_route_maps_rate_limit_to_stable_detail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")

    class _FailingExplain:
        def handle(self, *, project_id: str, insight_id: str, mode: str):
            _ = (project_id, insight_id, mode)
            raise LLMRateLimitError("llm_global_rate_limit_exceeded")

    app = create_app()
    object.__setattr__(app.state.container, "explain_insight", _FailingExplain())
    client = TestClient(app)

    response = client.get(
        "/v1/copilot/insights/abc/explain",
        headers={
            "X-SERVICE-KEY": "test-ai-service-key",
            "X-USER-ID": "u-1",
            "X-PROJECT-ID": "p-1",
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "copilot_rate_limited"


def test_copilot_route_maps_not_found_explicitly(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")

    class _MissingExplain:
        def handle(self, *, project_id: str, insight_id: str, mode: str):
            _ = (project_id, insight_id, mode)
            raise InsightNotFoundError("insight_not_found")

    app = create_app()
    object.__setattr__(app.state.container, "explain_insight", _MissingExplain())
    client = TestClient(app)

    response = client.get(
        "/v1/copilot/insights/abc/explain",
        headers={
            "X-SERVICE-KEY": "test-ai-service-key",
            "X-USER-ID": "u-1",
            "X-PROJECT-ID": "p-1",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Insight no encontrado"


def test_copilot_route_returns_shared_surface_metadata(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")

    class _ExplainOK:
        def handle(self, *, project_id: str, insight_id: str, mode: str):
            _ = project_id
            return {
                "insight_id": insight_id,
                "mode": mode,
                "explanation": {
                    "human_readable": "Resumen",
                    "audit_focused": "Auditoría",
                    "what_to_watch_next": "Seguimiento",
                },
                "proposal": None,
            }

    app = create_app()
    object.__setattr__(app.state.container, "explain_insight", _ExplainOK())
    client = TestClient(app)

    response = client.get(
        "/v1/copilot/insights/abc/explain",
        headers={
            "X-SERVICE-KEY": "test-ai-service-key",
            "X-USER-ID": "u-1",
            "X-PROJECT-ID": "p-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"]
    assert payload["output_kind"] == "copilot_explanation"
    assert payload["routed_agent"] == "copilot"
    assert payload["routing_source"] == "copilot_agent"
