# Ponti AI — v1.0.0

Servicio FastAPI + PostgreSQL para calcular insights determinísticos y ofrecer explainability acotada por insight vía LLM.

En la taxonomía canónica del ecosistema, Ponti AI combina:

- `InsightService`
- `CopilotAgent`

No expone hoy un `ProductAgent` general, y eso es deliberado.

## Endpoints

Siempre disponibles (sin auth):
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`

InsightService (requieren headers `X-SERVICE-KEY`, `X-USER-ID`, `X-PROJECT-ID`):
- `POST /v1/insights/compute`
- `GET  /v1/insights/summary`
- `GET  /v1/insights/{entity_type}/{entity_id}`
- `POST /v1/insights/{insight_id}/actions` — solo `ack`, `snooze`, `resolved`

CopilotAgent (solo si `COPILOT_ENABLED=true`, mismos headers):
- `GET /v1/copilot/insights/{insight_id}/explain`
- `GET /v1/copilot/insights/{insight_id}/why`
- `GET /v1/copilot/insights/{insight_id}/next-steps`

## Quickstart

```bash
# 1. Copiar config
cp .env.example .env

# 2. Levantar stack (DB + migraciones + API + Ollama)
make up

# 3. O ejecutar API local (requiere DB en ejecución)
make run

# 4. Correr tests
make test

# 5. Smoke test contra servicio en ejecución
make smoke-local
```

## Integración con frontend

Ponti Frontend no consume contratos AI escritos a mano.

- La fuente de verdad es el OpenAPI de Ponti AI.
- El frontend genera `ui/src/generated/ponti-ai.openapi.json` y
  `ui/src/generated/ponti-ai.openapi.ts` con
  `ui/scripts/generate-ai-types.mjs`.
- Los tipos estables consumibles por UI viven en `ui/src/types/ai.ts`.
- Los widgets visuales reutilizables de insights/copilot se consumen desde
  `@devpablocristo/modules-ai-console`.

Si cambia el contrato HTTP de Ponti AI, regenerar tipos en el frontend:

```bash
cd ../ponti-frontend/ui
node ./scripts/generate-ai-types.mjs
```

## Docker local

El `docker-compose.yml` del servicio usa `context: .` y `Dockerfile` local.
Ya no depende del layout padre ni de `Dockerfile.workspace` para el flujo
principal de desarrollo.

## Configuración

La config usa [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) con `env_ignore_empty=True`:

- Variables vacías (`LLM_API_KEY=`) se tratan como **no seteadas** y usan el default.
- Variables requeridas sin valor fallan al arranque con error claro.
- `LLM_MODEL` vacío se auto-resuelve según el provider (`stub` → `stub`, `openai` → `gpt-4o-mini`, etc.).
- Si `COPILOT_ENABLED=true` y `LLM_PROVIDER` no es `stub`, se exige `LLM_API_KEY` al arranque.

Ver `.env.example` para la lista completa de variables y defaults.

### Variables requeridas

| Variable | Descripción |
|---|---|
| `APP_NAME` | Nombre del servicio |
| `APP_ENV` | Entorno (`local`, `staging`, `production`) |
| `DB_DSN` | Connection string PostgreSQL |
| `AI_SERVICE_KEYS` | Lista CSV de API keys válidas |
| `STATEMENT_TIMEOUT_MS` | Timeout SQL en ms |
| `MAX_LIMIT` / `DEFAULT_LIMIT` | Límites de paginación SQL |
| `INSIGHTS_RATIO_HIGH` | Threshold ratio alto |
| `INSIGHTS_RATIO_MEDIUM` | Threshold ratio medio |
| `INSIGHTS_SPIKE_RATIO` | Threshold spike 7d vs 30d |
| `INSIGHTS_COOLDOWN_DAYS` | Días de cooldown por dedupe |
| `INSIGHTS_IMPACT_K` / `INSIGHTS_IMPACT_CAP` | Factores de impacto |
| `INSIGHTS_SIZE_SMALL_MAX` / `INSIGHTS_SIZE_MEDIUM_MAX` | Cohortes por hectáreas |

### Variables opcionales (con defaults)

| Variable | Default | Descripción |
|---|---|---|
| `COPILOT_ENABLED` | `true` | Kill switch del copilot LLM |
| `LLM_PROVIDER` | `stub` | `stub` / `ollama` / `openai` / `google_ai_studio` |
| `LLM_MODEL` | auto por provider | Modelo LLM |
| `LLM_API_KEY` | `None` | API key (requerida si provider != stub y copilot enabled) |
| `LLM_TIMEOUT_MS` | `5000` | Timeout LLM en ms |
| `LLM_MAX_RETRIES` | `3` | Reintentos LLM |
| `LLM_MAX_OUTPUT_TOKENS` | `700` | Tokens máximos de salida |
| `LLM_MAX_CALLS_PER_REQUEST` | `3` | Llamadas LLM por request |
| `LLM_BUDGET_TOKENS_PER_REQUEST` | `2500` | Budget de tokens por request |
| `LLM_RATE_LIMIT_RPS` | `2.0` | Rate limit global LLM |
| `DOMAIN` | `agriculture` | Dominio para prompts |
| `MAX_ACTIONS_ALLOWED` | `4` | Acciones máximas por propuesta |

## Seguridad LLM

- Output JSON validado con Pydantic schemas + tools allowlist + validación de args.
- No se loguean prompts completos; solo digest SHA256 + metadata.
- Timeout, rate limit global y presupuesto por request.
- Planner fail-open: si LLM falla, core sigue y la propuesta queda con `status=error`.

## Stack

- **Runtime**: Python 3.12 + FastAPI + Uvicorn
- **DB**: PostgreSQL 16
- **LLM**: Stub (local) / Ollama / OpenAI / Google AI Studio
- **Config**: Pydantic Settings (`env_ignore_empty=True`)
- **Migraciones**: golang-migrate
