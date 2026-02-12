TLDR:
1. Configurar `AI_SERVICE_KEYS` y parametros de insights en `.env`
2. `make up`
3. `make train-ml`
4. `make run`

# AI Copilot Service (v2)
Servicio AI read-only con FastAPI + PostgreSQL + pgvector. Arquitectura hexagonal liviana.

v2: Insights genera propuestas operativas (persistidas) via LLM con gating determinístico. Copilot pasa a ser capa de explainability (no chat libre).

## Requisitos
- Python 3.12+
- Docker + Docker Compose

## Configuracion local
Editar `.env` con las variables necesarias (DB_DSN, AI_SERVICE_KEYS, LLM_*, etc.).

## Levantar servicios con Docker
```bash
make up
```

### Ollama (local)
Este repo puede usar Ollama en local (Docker) como LLM provider.

1. Levantar Ollama:
```bash
docker compose up -d ollama
```

2. Descargar un modelo (ejemplo):
```bash
docker compose exec ollama ollama pull llama3.1
docker compose exec ollama ollama pull nomic-embed-text
```

3. Configurar `.env` para desarrollo local (si corrés la API fuera de Docker):
- `LLM_PROVIDER=ollama`
- `LLM_MODEL=llama3.1`
- `LLM_BASE_URL=http://localhost:11434`

Si corrés `ai-copilot` dentro de `docker compose`, se usa `LLM_BASE_URL=http://ollama:11434`.

### Google (cloud)
Para correr en la nube con Google AI Studio (Gemini API):
- `LLM_PROVIDER=google_ai_studio`
- `LLM_MODEL=gemini-flash-latest` (o cualquier `models/...` soportado)
- `LLM_API_KEY` via secret/variable de entorno del runtime (no en git)

## Ejecutar API en local
```bash
make run
```

## ML operativo (reglas + modelo)
El servicio combina insights de reglas con insights de ML cuando hay un modelo activo.

Variables clave:
- `ML_ENABLED=true`
- `ML_MODEL_TYPE=isolation_forest`
- `ML_MODELS_DIR=ml_models` (local) o `/app/ml_models` (docker)
- `ML_ROLLOUT_PERCENT=100` (0-100, gating gradual por proyecto)
- `ML_ENABLED_PROJECT_IDS=` (lista CSV opcional para allowlist estricta)
- `ML_SHADOW_MODE=false` (si `true`, persiste insights ML como `status=shadow` y no aparecen en listados de usuario)
- `ML_AUTO_PROMOTE=true` (promueve solo si el modelo nuevo mejora la calibracion)
- `ML_AUTO_RETRAIN_MIN_HOURS=24` (evita reentrenar demasiado seguido en modo automatico)
- `ML_PROMOTION_MIN_ALERT_RATE_IMPROVEMENT=0.01`
- `ML_PROMOTION_MIN_SAMPLES_RATIO=0.8`
- `EMBEDDING_PROVIDER=ollama` y `EMBEDDING_MODEL=nomic-embed-text` (embeddings reales para RAG)

Entrenar y activar modelo:
```bash
make train-ml
```

Con `docker compose`, los modelos quedan persistidos en el volumen `ai-ml-models`.

Contrato de features ML (`features-v1`):
- Training e inference usan el mismo catalogo SQL de features del runtime.
- El vector de entrada se normaliza con el contrato `{feature}_{window}` y zero-fill para faltantes.
- `project_id` se trata como `bigint`/texto canonico (sin casts a `uuid`).

Model registry (DB + filesystem):
- Artefactos (`model.joblib`, `pipeline.joblib`) se guardan en filesystem.
- Metadata/versionado/activacion se registran en `ai_ml_models` (PostgreSQL).
- `active.txt` se mantiene como fallback de compatibilidad.

Observabilidad ML:
- `GET /v1/ml/status` expone `rollout_percent`, `rollout_allowlist_size`, `last_drift_score`, `last_drift_level`.
- En `/metrics` se incrementan contadores `ml.drift.low|medium|high.count`.
- En `/metrics` se incrementan contadores `ml.rollout.skipped.count` e `insights.compute.ml_shadow.count`.

Calibracion supervisada:
- Durante training, si hay feedback suficiente en `ai_insight_actions`, se calcula `calibrated_threshold`.
- En inference, si el modelo activo tiene ese valor, se usa en lugar de `ML_ANOMALY_THRESHOLD`.

Estado de ML:
```bash
curl -s http://localhost:8090/v1/ml/status \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: 123" \
  -H "X-PROJECT-ID: demo-project"
```

Activar una version puntual:
```bash
curl -s -X POST http://localhost:8090/v1/ml/activate \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: admin" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{"version":"v1_20260206_120000"}'
```

Rollback a version previa (automatica):
```bash
curl -s -X POST http://localhost:8090/v1/ml/rollback \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: admin" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{}'
```

Rollback a version especifica:
```bash
curl -s -X POST http://localhost:8090/v1/ml/rollback \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: admin" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{"target_version":"v1_20260201_090000"}'
```

Retrain online (con lock):
```bash
curl -s -X POST http://localhost:8090/v1/jobs/retrain-ml \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: scheduler" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{
    "version": "v1_manual",
    "activate": true,
    "hyperparameters": { "contamination": 0.05, "n_estimators": 100 }
  }'
```

Retrain automatico (solo si el modelo activo esta "viejo"):
```bash
curl -s -X POST http://localhost:8090/v1/jobs/retrain-ml-if-needed \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: scheduler" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{"auto_promote": true}'
```

## Endpoints
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `GET /v1/ml/status`
- `POST /v1/ml/activate`
- `POST /v1/ml/rollback`
- `GET /v1/copilot/insights/{insight_id}/explain`
- `GET /v1/copilot/insights/{insight_id}/why`
- `GET /v1/copilot/insights/{insight_id}/next-steps`
- `POST /v1/rag/ingest`
- `POST /v1/insights/compute`
- `GET /v1/insights/{entity_type}/{entity_id}`
- `GET /v1/insights/summary`
- `POST /v1/insights/{insight_id}/actions`
- `POST /v1/jobs/recompute-active`
- `POST /v1/jobs/recompute-baselines`
- `POST /v1/jobs/recompute-queue/enqueue`
- `POST /v1/jobs/recompute-queue/process`
- `POST /v1/jobs/retrain-ml`
- `POST /v1/jobs/retrain-ml-if-needed`

## Operacion y calidad
- Runbook operativo: `docs/OPERATIONS_RUNBOOK.md`
- SLOs y alertas base: `docs/OBSERVABILIDAD_SLO.md`

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

Explainability:
- `GET /v1/copilot/insights/{insight_id}/explain|why|next-steps`

Propuestas (v2):
- Insights aplica gating determinístico (severity>=70, n_samples>=30, status=new, sin propuesta ok previa)
- Si pasa, llama a LLM planner y persiste la propuesta asociada al insight (audit/dedupe/repro).

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
curl -s http://localhost:8090/v1/copilot/insights/7e1bdc3e-6ec0-5814-9d7d-50c1d3486612/explain \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: 123" \
  -H "X-PROJECT-ID: demo-project"
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

Métricas relevantes en `/metrics`:
- `insights.compute.count`
- `insights.compute.rules_created`
- `insights.compute.ml_created`
