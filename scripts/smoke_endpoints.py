#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8090")
HEADERS = {
    "Content-Type": "application/json",
    "X-SERVICE-KEY": os.getenv("SMOKE_SERVICE_KEY", "servicekey123"),
    "X-USER-ID": os.getenv("SMOKE_USER_ID", "123"),
    "X-PROJECT-ID": os.getenv("SMOKE_PROJECT_ID", "1"),
}


def call(
    name: str,
    method: str,
    path: str,
    body: dict | None = None,
    auth: bool = False,
    timeout: int = 120,
) -> tuple[str, int, object]:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers.update(HEADERS)

    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.getcode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        code = exc.code
    except Exception as exc:  # noqa: BLE001
        raw = str(exc)
        code = 0

    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = raw
    return name, code, payload


def ok(code: int) -> bool:
    return 200 <= int(code) < 300


def main() -> int:
    results: list[tuple[str, int, object]] = []

    results.append(call("GET /healthz", "GET", "/healthz"))
    results.append(call("GET /readyz", "GET", "/readyz"))
    results.append(call("GET /metrics", "GET", "/metrics"))

    results.append(
        call(
            "POST /v1/jobs/recompute-baselines",
            "POST",
            "/v1/jobs/recompute-baselines",
            {"batch_size": 200},
            auth=True,
        )
    )
    results.append(call("POST /v1/insights/compute", "POST", "/v1/insights/compute", {}, auth=True))

    summary = call("GET /v1/insights/summary", "GET", "/v1/insights/summary", auth=True)
    project = call("GET /v1/insights/project/1", "GET", "/v1/insights/project/1", auth=True)
    results.append(summary)
    results.append(project)

    insight_id = None
    if ok(summary[1]) and isinstance(summary[2], dict):
        top = summary[2].get("top_insights", [])
        if top:
            insight_id = top[0].get("id")
    if not insight_id and ok(project[1]) and isinstance(project[2], dict):
        insights = project[2].get("insights", [])
        if insights:
            insight_id = insights[0].get("id")

    if insight_id:
        results.append(
            call(
                "GET /v1/copilot/insights/{id}/explain",
                "GET",
                f"/v1/copilot/insights/{insight_id}/explain",
                auth=True,
                timeout=180,
            )
        )
        results.append(
            call(
                "GET /v1/copilot/insights/{id}/why",
                "GET",
                f"/v1/copilot/insights/{insight_id}/why",
                auth=True,
                timeout=180,
            )
        )
        results.append(
            call(
                "GET /v1/copilot/insights/{id}/next-steps",
                "GET",
                f"/v1/copilot/insights/{insight_id}/next-steps",
                auth=True,
                timeout=180,
            )
        )
        results.append(
            call(
                "POST /v1/insights/{id}/actions",
                "POST",
                f"/v1/insights/{insight_id}/actions",
                {"action": "acknowledged", "new_status": "acknowledged"},
                auth=True,
            )
        )
    else:
        results.append(("COPILOT/ACTIONS", 0, "No se encontró insight_id para pruebas de copilot/actions"))

    results.append(
        call(
            "POST /v1/jobs/recompute-active",
            "POST",
            "/v1/jobs/recompute-active",
            {"batch_size": 50},
            auth=True,
        )
    )
    results.append(
        call(
            "POST /v1/jobs/retrain-ml",
            "POST",
            "/v1/jobs/retrain-ml",
            {"activate": True},
            auth=True,
            timeout=300,
        )
    )
    results.append(
        call(
            "POST /v1/jobs/retrain-ml-if-needed",
            "POST",
            "/v1/jobs/retrain-ml-if-needed",
            {},
            auth=True,
            timeout=300,
        )
    )
    ml_status = call("GET /v1/ml/status", "GET", "/v1/ml/status", auth=True)
    results.append(ml_status)

    active_version = None
    if ok(ml_status[1]) and isinstance(ml_status[2], dict):
        active_version = ml_status[2].get("active_version")
    results.append(
        call(
            "POST /v1/ml/activate",
            "POST",
            "/v1/ml/activate",
            {"version": active_version or "latest"},
            auth=True,
        )
    )
    results.append(call("POST /v1/ml/rollback", "POST", "/v1/ml/rollback", {}, auth=True))
    results.append(
        call(
            "POST /v1/rag/ingest",
            "POST",
            "/v1/rag/ingest",
            {
                "documents": [
                    {
                        "source": "smoke-test",
                        "title": "Costo semanal",
                        "content": "Si costo semanal supera 2x promedio mensual, revisar desviaciones.",
                    }
                ]
            },
            auth=True,
            timeout=120,
        )
    )

    failures = []
    for name, code, payload in results:
        status = "OK" if ok(code) else "FAIL"
        print(f"{status} {code} {name}")
        if status == "FAIL":
            failures.append((name, code, payload))
            print(f"  payload: {str(payload)[:500]}")

    print(f"TOTAL {len(results)} FAILS {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
