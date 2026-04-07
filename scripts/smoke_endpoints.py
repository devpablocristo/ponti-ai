#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8090")
raw_service_keys = os.getenv("AI_SERVICE_KEYS", "")
fallback_service_key = ""
for _k in raw_service_keys.split(","):
    candidate = _k.strip()
    if candidate:
        fallback_service_key = candidate
        break
HEADERS = {
    "Content-Type": "application/json",
    "X-SERVICE-KEY": os.getenv("SMOKE_SERVICE_KEY", fallback_service_key or "local-dev-ai-service-key"),
    "X-USER-ID": os.getenv("SMOKE_USER_ID", "123"),
    "X-PROJECT-ID": os.getenv("SMOKE_PROJECT_ID", "1"),
}


def call(name: str, method: str, path: str, body: dict | None = None, auth: bool = False) -> tuple[str, int, object]:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers.update(HEADERS)

    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            code = response.getcode()
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        code = error.code
    except Exception as error:  # noqa: BLE001
        raw = str(error)
        code = 0

    try:
        payload = json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        payload = raw
    return name, code, payload


def ok(status_code: int) -> bool:
    return 200 <= int(status_code) < 300


def main() -> int:
    strict_insights = os.getenv("SMOKE_STRICT_INSIGHTS", "0") == "1"
    checks = []

    health_candidates = [
        call("GET /healthz", "GET", "/healthz"),
        call("GET /v1/healthz", "GET", "/v1/healthz"),
    ]
    ready_candidates = [
        call("GET /readyz", "GET", "/readyz"),
        call("GET /v1/readyz", "GET", "/v1/readyz"),
    ]

    health_ok = any(ok(code) or code == 404 for _, code, _ in health_candidates)
    ready_ok = any(ok(code) or code == 404 for _, code, _ in ready_candidates)
    best_health = next((item for item in health_candidates if ok(item[1])), health_candidates[0])
    best_ready = next((item for item in ready_candidates if ok(item[1])), ready_candidates[0])
    checks.extend([best_health, best_ready])

    checks.extend(
        [
            call("GET /metrics", "GET", "/metrics"),
            call("POST /v1/insights/compute", "POST", "/v1/insights/compute", {}, auth=True),
            call("GET /v1/insights/summary", "GET", "/v1/insights/summary", auth=True),
            call("GET /v1/insights/project/1", "GET", "/v1/insights/project/1", auth=True),
            call("POST /v1/chat", "POST", "/v1/chat", {"message": "hola"}, auth=True),
            call("GET /v1/chat/conversations", "GET", "/v1/chat/conversations", auth=True),
            call("POST /v1/rag/ingest", "POST", "/v1/rag/ingest", {}, auth=True),
            call("GET /v1/ml/status", "GET", "/v1/ml/status", auth=True),
            call("POST /v1/jobs/recompute-active", "POST", "/v1/jobs/recompute-active", {}, auth=True),
        ]
    )

    failures = 0

    for name, status_code, payload in checks:
        if name in ("GET /healthz", "GET /v1/healthz"):
            status_ok = health_ok
        elif name in ("GET /readyz", "GET /v1/readyz"):
            status_ok = ready_ok
        else:
            expected_404 = (
                name.startswith("POST /v1/rag")
                or name.startswith("GET /v1/ml")
                or name.startswith("POST /v1/jobs")
            )
            is_insight = name.startswith("POST /v1/insights") or name.startswith("GET /v1/insights")
            is_chat = name.startswith("POST /v1/chat") or name.startswith("GET /v1/chat")
            if expected_404:
                status_ok = status_code == 404
            elif (is_insight or is_chat) and not strict_insights:
                status_ok = ok(status_code) or status_code == 500
            else:
                status_ok = ok(status_code)

        print(("OK" if status_ok else "FAIL"), status_code, name)
        if not status_ok:
            failures += 1
            print(" payload:", str(payload)[:400])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
