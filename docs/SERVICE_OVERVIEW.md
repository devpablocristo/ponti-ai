# Service Overview — v1.0.0

## Qué es

En la taxonomía canónica del ecosistema, Ponti AI se expresa como:

- `InsightService`
- `CopilotAgent`

No modela hoy un `ProductAgent` general, y eso es intencional.

Ponti AI es una API FastAPI que:
1. Calcula **insights determinísticos**: compara features de un proyecto contra baselines (percentiles p75/p90) y detecta spikes temporales.
2. Ofrece **explainability acotada por insight** vía LLM (`CopilotAgent`), con propuestas no vinculantes y explicaciones en 3 modos.
3. Persiste resultados técnicos en tablas `ai_*` para seguimiento operativo.

## Arquitectura

```
Cliente → FastAPI (routes) → Use Cases (domain) → Ports (interfaces)
                                                       ↓
                                              Adapters (DB, LLM, SQL)
```

- **Hexagonal**: ports en `contexts/*/application/ports/`, adapters en `adapters/outbound/`.
- **Config**: Pydantic Settings con `env_ignore_empty=True` (variables vacías usan defaults).
- **LLM**: fail-open para propuesta/planning de insights; si falla esa capa, el cómputo determinístico sigue y la propuesta queda `status=error`.

## Endpoints públicos

### Siempre disponibles (sin auth)

| Método | Path | Descripción |
|---|---|---|
| GET | `/healthz` | Liveness check |
| GET | `/readyz` | Readiness check (verifica DB) |
| GET | `/metrics` | Contadores y timers in-memory |

### InsightService (requiere `X-SERVICE-KEY`, `X-USER-ID`, `X-PROJECT-ID`)

| Método | Path | Descripción |
|---|---|---|
| POST | `/v1/insights/compute` | Calcula insights para un proyecto |
| GET | `/v1/insights/summary` | Resumen: conteos + top insights |
| GET | `/v1/insights/{entity_type}/{entity_id}` | Lista insights por entidad |
| POST | `/v1/insights/{insight_id}/actions` | Registra acción humana (ack/snooze/resolved) |

### CopilotAgent (solo si `COPILOT_ENABLED=true`)

| Método | Path | Descripción |
|---|---|---|
| GET | `/v1/copilot/insights/{insight_id}/explain` | Explicación operativa |
| GET | `/v1/copilot/insights/{insight_id}/why` | Motivo de negocio |
| GET | `/v1/copilot/insights/{insight_id}/next-steps` | Siguientes pasos |

Cada endpoint de `CopilotAgent` devuelve:
```json
{
  "insight_id": "...",
  "mode": "explain|why|next-steps",
  "explanation": {
    "human_readable": "...",
    "audit_focused": "...",
    "what_to_watch_next": "..."
  },
  "proposal": { ... }
}
```

## Tablas

| Tabla | Descripción |
|---|---|
| `ai_audit_logs` | Log de auditoría de operaciones |
| `ai_insights` | Insights calculados |
| `ai_insight_actions` | Acciones humanas sobre insights |
| `ai_baselines` | Baselines estadísticos (p50/p75/p90) |
| `ai_insight_proposals` | Propuestas LLM por insight |

## Variables de entorno

### Requeridas (fallan al arranque si no están)

`APP_NAME`, `APP_ENV`, `DB_DSN`, `AI_SERVICE_KEYS`, `STATEMENT_TIMEOUT_MS`, `MAX_LIMIT`, `DEFAULT_LIMIT`, `INSIGHTS_RATIO_HIGH`, `INSIGHTS_RATIO_MEDIUM`, `INSIGHTS_SPIKE_RATIO`, `INSIGHTS_COOLDOWN_DAYS`, `INSIGHTS_IMPACT_K`, `INSIGHTS_IMPACT_CAP`, `INSIGHTS_SIZE_SMALL_MAX`, `INSIGHTS_SIZE_MEDIUM_MAX`

### Opcionales (con defaults)

| Variable | Default | Nota |
|---|---|---|
| `COPILOT_ENABLED` | `true` | Kill switch |
| `LLM_PROVIDER` | `stub` | `stub`/`ollama`/`openai`/`google_ai_studio` |
| `LLM_MODEL` | auto | Se resuelve por provider si está vacío |
| `LLM_API_KEY` | `None` | Requerida si `COPILOT_ENABLED=true` y `LLM_PROVIDER!=stub` |
| `LLM_TIMEOUT_MS` | `5000` | Min: 1 |
| `LLM_MAX_RETRIES` | `3` | Min: 1 |
| `LLM_MAX_OUTPUT_TOKENS` | `700` | Min: 1 |
| `LLM_MAX_CALLS_PER_REQUEST` | `3` | Budget calls por request |
| `LLM_BUDGET_TOKENS_PER_REQUEST` | `2500` | Budget tokens por request |
| `LLM_RATE_LIMIT_RPS` | `2.0` | Min: 0.1 |
| `DOMAIN` | `agriculture` | Dominio para prompts LLM |
| `MAX_ACTIONS_ALLOWED` | `4` | Acciones máx en propuesta |

### Comportamiento de `env_ignore_empty`

La config usa `pydantic-settings` con `env_ignore_empty=True`:
- `LLM_API_KEY=` (vacío) → se trata como `None` (usa el default)
- `LLM_MODEL=` (vacío) → se auto-resuelve por provider
- No más fallos en runtime por strings vacías

## Seguridad LLM

- Output JSON validado con Pydantic strict schemas (`extra="forbid"`)
- Tools allowlist: solo `request_cost_breakdown` y `create_review_task`
- Validación de `tool_args` contra schema antes de persistir
- Logging seguro: digest SHA256 del prompt, nunca el texto completo
- Rate limit global in-memory (configurable vía `LLM_RATE_LIMIT_RPS`)
- Budget por request: máx calls + máx tokens estimados
- Timeout por llamada LLM
