#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${E2E_BASE_URL:-http://localhost:8090}"
OLLAMA_URL="${E2E_OLLAMA_URL:-http://localhost:11434}"
SERVICE_KEY="${E2E_SERVICE_KEY:-servicekey123}"
USER_ID="${E2E_USER_ID:-e2e-full}"
PROJECT_ID="${E2E_PROJECT_ID:-1}"
PROJECT2_ID="${E2E_PROJECT2_ID:-2}"

DEFAULT_TIMEOUT="${E2E_TIMEOUT_S:-40}"
COPILOT_TIMEOUT="${E2E_COPILOT_TIMEOUT_S:-60}"
ML_TIMEOUT="${E2E_ML_TIMEOUT_S:-120}"
CONCURRENCY="${E2E_CONCURRENCY:-5}"

PASS=0
FAIL=0
SKIP=0

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required"
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required"
  exit 2
fi

AUTH_HEADERS=(-H "X-SERVICE-KEY: ${SERVICE_KEY}" -H "X-USER-ID: ${USER_ID}" -H "X-PROJECT-ID: ${PROJECT_ID}")
AUTH_HEADERS_P2=(-H "X-SERVICE-KEY: ${SERVICE_KEY}" -H "X-USER-ID: ${USER_ID}" -H "X-PROJECT-ID: ${PROJECT2_ID}")

ok() {
  PASS=$((PASS + 1))
  echo "OK   $1"
}

ko() {
  FAIL=$((FAIL + 1))
  echo "FAIL $1"
}

skip() {
  SKIP=$((SKIP + 1))
  echo "SKIP $1"
}

request() {
  local name="$1"
  local method="$2"
  local path="$3"
  local expected="$4"
  local auth="$5"
  local timeout="${6:-$DEFAULT_TIMEOUT}"
  local body="${7:-}"
  local tmp
  tmp="$(mktemp)"

  local -a headers=()
  if [[ "${auth}" == "p1" ]]; then
    headers=("${AUTH_HEADERS[@]}")
  elif [[ "${auth}" == "p2" ]]; then
    headers=("${AUTH_HEADERS_P2[@]}")
  fi

  local code
  if [[ -n "${body}" ]]; then
    code="$(curl -sS --max-time "${timeout}" -o "${tmp}" -w "%{http_code}" -X "${method}" "${BASE_URL}${path}" "${headers[@]}" -H "Content-Type: application/json" -d "${body}" || true)"
  else
    code="$(curl -sS --max-time "${timeout}" -o "${tmp}" -w "%{http_code}" -X "${method}" "${BASE_URL}${path}" "${headers[@]}" || true)"
  fi

  if [[ "${code}" == "${expected}" ]]; then
    ok "${name}"
  else
    ko "${name} (got=${code} expected=${expected}) body=$(head -c 220 "${tmp}")"
  fi
  rm -f "${tmp}"
}

wait_ready() {
  local retries=30
  local sleep_s=1
  for _i in $(seq 1 "${retries}"); do
    if curl -sS --max-time 3 "${BASE_URL}/healthz" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_s}"
  done
  echo "Service not ready at ${BASE_URL}/healthz after ${retries}s"
  exit 1
}

wait_ready

echo "== Basic health =="
request "healthz" GET "/healthz" "200" "none"
request "readyz" GET "/readyz" "200" "none"
request "metrics" GET "/metrics" "200" "none"

echo "== Auth negatives =="
request "auth missing all" GET "/v1/insights/summary" "401" "none"
tmp_auth="$(mktemp)"
code_auth="$(curl -sS --max-time "${DEFAULT_TIMEOUT}" -o "${tmp_auth}" -w "%{http_code}" -H "X-SERVICE-KEY: bad" -H "X-USER-ID: ${USER_ID}" -H "X-PROJECT-ID: ${PROJECT_ID}" "${BASE_URL}/v1/insights/summary" || true)"
if [[ "${code_auth}" == "403" ]]; then
  ok "auth bad key"
else
  ko "auth bad key (got=${code_auth} expected=403) body=$(head -c 220 "${tmp_auth}")"
fi
rm -f "${tmp_auth}"

echo "== Ollama direct =="
OLLAMA_TAGS="$(curl -sS --max-time "${DEFAULT_TIMEOUT}" "${OLLAMA_URL}/api/tags" || true)"
HAS_OLLAMA_CHAT_MODEL=0
HAS_OLLAMA_EMBED_MODEL=0
if echo "${OLLAMA_TAGS}" | jq -e '.models // [] | map(.name) | any(startswith("llama3.1"))' >/dev/null 2>&1; then
  HAS_OLLAMA_CHAT_MODEL=1
fi
if echo "${OLLAMA_TAGS}" | jq -e '.models // [] | map(.name) | any(startswith("nomic-embed-text"))' >/dev/null 2>&1; then
  HAS_OLLAMA_EMBED_MODEL=1
fi

tmp_ollama="$(mktemp)"
if [[ "${HAS_OLLAMA_CHAT_MODEL}" == "1" ]]; then
  code_ollama="$(curl -sS --max-time "${COPILOT_TIMEOUT}" -o "${tmp_ollama}" -w "%{http_code}" -X POST "${OLLAMA_URL}/api/chat" -H "Content-Type: application/json" -d '{"model":"llama3.1","stream":false,"messages":[{"role":"user","content":"Respond in JSON: {\"ok\":true}"}],"format":"json"}' || true)"
  if [[ "${code_ollama}" == "200" ]] && jq -e '.message.content|length>0' "${tmp_ollama}" >/dev/null 2>&1; then
    ok "ollama chat"
  else
    ko "ollama chat (got=${code_ollama}) body=$(head -c 220 "${tmp_ollama}")"
  fi
else
  skip "ollama chat (model llama3.1 missing)"
fi
rm -f "${tmp_ollama}"

tmp_embed="$(mktemp)"
if [[ "${HAS_OLLAMA_EMBED_MODEL}" == "1" ]]; then
  code_embed="$(curl -sS --max-time "${DEFAULT_TIMEOUT}" -o "${tmp_embed}" -w "%{http_code}" -X POST "${OLLAMA_URL}/api/embeddings" -H "Content-Type: application/json" -d '{"model":"nomic-embed-text","prompt":"hola"}' || true)"
  if [[ "${code_embed}" == "200" ]] && jq -e '.embedding|length>0' "${tmp_embed}" >/dev/null 2>&1; then
    ok "ollama embeddings"
  else
    ko "ollama embeddings (got=${code_embed}) body=$(head -c 220 "${tmp_embed}")"
  fi
else
  skip "ollama embeddings (model nomic-embed-text missing)"
fi
rm -f "${tmp_embed}"

echo "== Insights + Copilot + RAG + Jobs =="
request "baselines p1" POST "/v1/jobs/recompute-baselines" "200" "p1" "${DEFAULT_TIMEOUT}" "{}"
request "compute p1" POST "/v1/insights/compute" "200" "p1"
request "summary p1" GET "/v1/insights/summary" "200" "p1"
request "insights project p1" GET "/v1/insights/project/1" "200" "p1"

INSIGHT_ID="$(curl -sS --max-time "${DEFAULT_TIMEOUT}" "${AUTH_HEADERS[@]}" "${BASE_URL}/v1/insights/summary" | jq -r '.top_insights[0].id')"
if [[ -n "${INSIGHT_ID}" && "${INSIGHT_ID}" != "null" ]]; then
  ok "insight id available"
else
  ko "insight id unavailable"
fi

request "action valid" POST "/v1/insights/${INSIGHT_ID}/actions" "200" "p1" "${DEFAULT_TIMEOUT}" '{"action":"ack","new_status":"acknowledged"}'
request "action invalid payload" POST "/v1/insights/${INSIGHT_ID}/actions" "422" "p1" "${DEFAULT_TIMEOUT}" '{"action":"","new_status":"acknowledged"}'
request "action missing insight" POST "/v1/insights/not-found/actions" "404" "p1" "${DEFAULT_TIMEOUT}" '{"action":"ack","new_status":"acknowledged"}'

request "copilot explain" GET "/v1/copilot/insights/${INSIGHT_ID}/explain" "200" "p1" "${COPILOT_TIMEOUT}"
request "copilot why" GET "/v1/copilot/insights/${INSIGHT_ID}/why" "200" "p1" "${COPILOT_TIMEOUT}"
request "copilot next-steps" GET "/v1/copilot/insights/${INSIGHT_ID}/next-steps" "200" "p1" "${COPILOT_TIMEOUT}"
request "copilot missing insight" GET "/v1/copilot/insights/not-found/explain" "404" "p1"

if [[ "${HAS_OLLAMA_EMBED_MODEL}" == "1" ]]; then
  request "rag ingest valid" POST "/v1/rag/ingest" "200" "p1" "${DEFAULT_TIMEOUT}" '{"documents":[{"source":"e2e","title":"doc","content":"contenido","metadata":{"k":"v"}}]}'
else
  skip "rag ingest valid (embedding model missing)"
fi
request "rag ingest invalid payload" POST "/v1/rag/ingest" "422" "p1" "${DEFAULT_TIMEOUT}" '{"documents":[{"source":"e2e","title":"doc"}]}'

request "queue enqueue" POST "/v1/jobs/recompute-queue/enqueue" "200" "p1" "${DEFAULT_TIMEOUT}" '{"source":"e2e","reason":"full","debounce_seconds":0}'
request "queue enqueue invalid debounce" POST "/v1/jobs/recompute-queue/enqueue" "422" "p1" "${DEFAULT_TIMEOUT}" '{"source":"e2e","reason":"full","debounce_seconds":90000}'
request "queue process" POST "/v1/jobs/recompute-queue/process" "200" "p1" "${DEFAULT_TIMEOUT}" '{"limit":10,"workers":2}'
request "queue process invalid" POST "/v1/jobs/recompute-queue/process" "422" "p1" "${DEFAULT_TIMEOUT}" '{"limit":0,"workers":2}'
request "recompute active" POST "/v1/jobs/recompute-active" "200" "p1" "${DEFAULT_TIMEOUT}" "{}"

echo "== ML =="
request "ml status" GET "/v1/ml/status" "200" "p1"
ML_RETRAIN_PAYLOAD="$(curl -sS --max-time "${ML_TIMEOUT}" -X POST "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" -d '{"activate":false,"auto_promote":false}' "${BASE_URL}/v1/jobs/retrain-ml" || true)"
ML_RETRAIN_STATUS="$(echo "${ML_RETRAIN_PAYLOAD}" | jq -r '.status // ""' 2>/dev/null || true)"
NEW_VERSION="$(echo "${ML_RETRAIN_PAYLOAD}" | jq -r '.model_version // ""' 2>/dev/null || true)"
ML_RETRAIN_ERROR="$(echo "${ML_RETRAIN_PAYLOAD}" | jq -r '.error // ""' 2>/dev/null || true)"
if [[ "${ML_RETRAIN_STATUS}" == "ok" ]]; then
  ok "ml retrain"
  if [[ -n "${NEW_VERSION}" && "${NEW_VERSION}" != "null" ]]; then
    ok "ml new version"
  else
    ko "ml new version missing"
  fi
elif [[ "${ML_RETRAIN_STATUS}" == "error" && "${ML_RETRAIN_ERROR}" == *"Muy pocos datos para entrenar"* ]]; then
  skip "ml retrain (insufficient samples in seed dataset)"
  skip "ml new version (insufficient samples in seed dataset)"
else
  ko "ml retrain unexpected response: ${ML_RETRAIN_PAYLOAD}"
fi
request "ml activate invalid version" POST "/v1/ml/activate" "200" "p1" "${DEFAULT_TIMEOUT}" '{"version":"v__missing"}'
if [[ -n "${NEW_VERSION}" && "${NEW_VERSION}" != "null" ]]; then
  request "ml activate valid version" POST "/v1/ml/activate" "200" "p1" "${DEFAULT_TIMEOUT}" "{\"version\":\"${NEW_VERSION}\"}"
else
  skip "ml activate valid version (no trained model version)"
fi
request "ml rollback" POST "/v1/ml/rollback" "200" "p1" "${DEFAULT_TIMEOUT}" "{}"
request "ml retrain if needed" POST "/v1/jobs/retrain-ml-if-needed" "200" "p1" "${ML_TIMEOUT}" '{"activate":false,"auto_promote":false}'

echo "== Project isolation =="
request "summary p2" GET "/v1/insights/summary" "200" "p2"
request "compute p2" POST "/v1/insights/compute" "200" "p2"
request "recompute p2" POST "/v1/jobs/recompute-active" "200" "p2" "${DEFAULT_TIMEOUT}" "{}"

echo "== Concurrency burst =="
for i in $(seq 1 "${CONCURRENCY}"); do
  (
    curl -sS --max-time "${COPILOT_TIMEOUT}" "${AUTH_HEADERS[@]}" "${BASE_URL}/v1/copilot/insights/${INSIGHT_ID}/explain" >/tmp/e2e_full_cop_"${i}".json \
    && echo ok >/tmp/e2e_full_cop_"${i}".st || echo fail >/tmp/e2e_full_cop_"${i}".st
  ) &
  (
    curl -sS --max-time "${DEFAULT_TIMEOUT}" -X POST "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" -d '{}' "${BASE_URL}/v1/jobs/recompute-active" >/tmp/e2e_full_job_"${i}".json \
    && echo ok >/tmp/e2e_full_job_"${i}".st || echo fail >/tmp/e2e_full_job_"${i}".st
  ) &
done
wait

for i in $(seq 1 "${CONCURRENCY}"); do
  if rg -q "ok" /tmp/e2e_full_cop_"${i}".st; then ok "concurrent copilot ${i}"; else ko "concurrent copilot ${i}"; fi
  if rg -q "ok" /tmp/e2e_full_job_"${i}".st; then ok "concurrent job ${i}"; else ko "concurrent job ${i}"; fi
done
rm -f /tmp/e2e_full_cop_*.json /tmp/e2e_full_cop_*.st /tmp/e2e_full_job_*.json /tmp/e2e_full_job_*.st || true

echo "== Logs sanity =="
if docker compose logs --since=20m ai-copilot | rg -q "500 Internal Server Error|Traceback|Exception in ASGI"; then
  ko "log sanity (unexpected server error found)"
else
  ok "log sanity"
fi

echo "PASS=${PASS} FAIL=${FAIL} SKIP=${SKIP}"
if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
