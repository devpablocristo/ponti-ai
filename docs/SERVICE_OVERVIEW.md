# Service Overview (MVP)

## Qué es
`ponti-ai` es una API FastAPI que calcula insights determinísticos desde consultas SQL read-only sobre PostgreSQL y persiste resultados técnicos (`ai_*`) para seguimiento operativo y explainability acotada por insight.

## Endpoints públicos

Siempre disponibles:
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`

Insights:
- `POST /v1/insights/compute`
- `GET /v1/insights/summary`
- `GET /v1/insights/{entity_type}/{entity_id}`
- `POST /v1/insights/{insight_id}/actions`

Copilot (solo cuando `COPILOT_ENABLED=true`):
- `GET /v1/copilot/insights/{insight_id}/explain`
- `GET /v1/copilot/insights/{insight_id}/why`
- `GET /v1/copilot/insights/{insight_id}/next-steps`

## Variables de entorno mínimas
- `APP_NAME`
- `APP_ENV`
- `DB_DSN`
- `AI_SERVICE_KEYS`
- `STATEMENT_TIMEOUT_MS`
- `MAX_LIMIT`
- `DEFAULT_LIMIT`
- `COPILOT_ENABLED`
- `LLM_PROVIDER`
- `LLM_MODEL`
- `LLM_API_KEY` (si provider no es `stub`)
- `LLM_BASE_URL` (según provider)
- `LLM_TIMEOUT_MS` (default 5000)
- `LLM_MAX_OUTPUT_TOKENS` (default 700)
- `LLM_MAX_CALLS_PER_REQUEST` (default 3)
- `LLM_BUDGET_TOKENS_PER_REQUEST` (default 2500)
- `LLM_RATE_LIMIT_RPS` (default 2.0)
- `INSIGHTS_RATIO_HIGH`
- `INSIGHTS_RATIO_MEDIUM`
- `INSIGHTS_SPIKE_RATIO`
- `INSIGHTS_COOLDOWN_DAYS`
- `INSIGHTS_IMPACT_K`
- `INSIGHTS_IMPACT_CAP`
- `INSIGHTS_SIZE_SMALL_MAX`
- `INSIGHTS_SIZE_MEDIUM_MAX`
- `DOMAIN`
- `MAX_ACTIONS_ALLOWED`

## Estado del producto MVP
El MVP no incluye módulos ni rutas de:
- RAG (`/v1/rag/*`)
- ML (`/v1/ml/*`)
- Jobs/Queue (`/v1/jobs/*`)

Estos componentes fueron removidos del producto MVP y no forman parte de la superficie pública.
