TLDR:
1. `cp .env.example .env`
2. Configurar `AI_SERVICE_KEYS` y parametros de insights en `.env`
3. `make up`
4. `make run`

# AI Copilot Service (MVP)
Servicio AI read-only con FastAPI + PostgreSQL + pgvector. Arquitectura hexagonal liviana.

## Requisitos
- Python 3.12+
- Docker + Docker Compose

## Configuracion local
```bash
cp .env.example .env
```

## Levantar servicios con Docker
```bash
make up
```

## Ejecutar API en local
```bash
make run
```

## Endpoints
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `POST /v1/ask`
- `POST /v1/rag/ingest`
- `POST /v1/insights/compute`
- `GET /v1/insights/{entity_type}/{entity_id}`
- `GET /v1/insights/summary`
- `POST /v1/insights/{insight_id}/actions`
- `POST /v1/jobs/recompute-active`
- `POST /v1/jobs/recompute-baselines`

## Headers requeridos
```
X-SERVICE-KEY: servicekey123
X-USER-ID: 123
X-PROJECT-ID: demo-project
```

## Insights (baseline + timing)
Las alertas comparan el valor del proyecto contra percentiles:
- Baseline propio (historial del proyecto)
- Baseline por cohorte (size=small|medium|large)

Reglas principales:
- Percentiles p75/p90
- Spike (7d vs 30d)

Parametros:
- `INSIGHTS_RATIO_HIGH`, `INSIGHTS_RATIO_MEDIUM`
- `INSIGHTS_SPIKE_RATIO`
- `INSIGHTS_COOLDOWN_DAYS`
- `INSIGHTS_IMPACT_K`, `INSIGHTS_IMPACT_CAP`

Salida extendida por insight:
- `impact_min`, `impact_max`, `impact_unit`
- `confidence`
- `dedupe_key`, `cooldown_until`
- `action_json` con `action_type`, `action_params`, `suggested_due_date`, `cta_label`

Integracion Copilot:
`/v1/ask` incluye `related_insights_count` y `related_insights` (top 3).

## Diagrama de flujo
```
FE (UI)
 → BFF (ponti-frontend/api, valida JWT)
 → Backend Go (proxy seguro)
 → AI Service (FastAPI, READ-ONLY)
```

## Ejemplo de insight
```json
{
  "title": "cost_total alto vs baseline",
  "type": "anomaly",
  "severity": 80,
  "impact_min": 0.35,
  "impact_max": 0.65,
  "impact_unit": "%",
  "confidence": "high",
  "action": {
    "action_type": "review_inputs",
    "action_params": { "feature": "cost_total", "window": "all" },
    "suggested_due_date": "2026-02-07",
    "cta_label": "Revisar costos"
  }
}
```

## Arquitectura (hexagonal liviana)
- `domain/`: entidades y value objects
- `application/`: use cases + ports
- `adapters/inbound/`: API (FastAPI) + schemas + auth
- `adapters/outbound/`: DB, SQL, RAG, modelos, observabilidad
- `app/main.py`: wiring manual (sin DI framework)

## Ejemplos curl
```bash
curl -s http://localhost:8090/healthz
```

```bash
curl -s http://localhost:8090/readyz
```

```bash
curl -s -X POST http://localhost:8090/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: 123" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{
    "question": "Necesito el resumen del proyecto",
    "context": { "date_from": "2025-01-01", "date_to": "2025-12-31" }
  }'
```

```bash
curl -s -X POST http://localhost:8090/v1/rag/ingest \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: 123" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{
    "documents": [
      { "source": "manual", "title": "Guia", "content": "Contenido de prueba" }
    ]
  }'
```

```bash
curl -s -X POST http://localhost:8090/v1/insights/compute \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: 123" \
  -H "X-PROJECT-ID: demo-project"
```

```bash
curl -s http://localhost:8090/v1/insights/summary \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: 123" \
  -H "X-PROJECT-ID: demo-project"
```

## Badge / notificaciones (sin push)
El FE puede usar `GET /v1/insights/summary` para obtener:
- `new_count_total`
- `new_count_high_severity`
- top 3 insights

## Cloud Scheduler (ejemplo)
```bash
curl -s -X POST http://localhost:8090/v1/jobs/recompute-active \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: scheduler" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{ "batch_size": 100 }'
```

## Tests
```bash
make test
```
