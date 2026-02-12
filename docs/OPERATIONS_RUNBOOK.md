# Runbook Operativo - AI Copilot

## Objetivo
Guia operativa para incidentes comunes, degradacion controlada y recovery.

## Pre-check diario
1. `GET /healthz` debe responder `{"status":"ok"}`.
2. `GET /readyz` debe responder `{"status":"ok"}`.
3. `GET /v1/ml/status`:
   - `enabled=true` si ML debe estar activo.
   - `has_active_model=true` en ventanas productivas.
4. `GET /metrics`:
   - revisar `insights.compute.count` y `insights.compute.duration_ms`.
   - revisar `ml.drift.high.count` y `ml.rollout.skipped.count`.

## Incidente: API no lista (`/readyz` 503)
1. Verificar DB:
   - `docker compose ps`
   - `docker compose logs ai-db --tail=200`
2. Verificar `DB_DSN` efectivo en runtime.
3. Si hay migraciones pendientes:
   - `make migrate`
4. Revalidar:
   - `GET /readyz`

## Incidente: errores de planner/LLM
1. Confirmar proveedor/modelo:
   - `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`.
2. Aislar impacto operativo:
   - El compute de insights es fail-open; reglas deben seguir activas.
3. Revisar logs:
   - eventos `llm.request` y errores `LLM HTTP`.
4. Mitigacion:
   - temporalmente `LLM_PROVIDER=stub` para continuidad.

## Incidente: drift ML alto
1. Revisar `GET /v1/ml/status`:
   - `last_drift_level`, `last_drift_score`.
2. Ejecutar retrain:
   - `POST /v1/jobs/retrain-ml-if-needed`
3. Si persiste:
   - `POST /v1/jobs/retrain-ml` con hiperparametros controlados.
4. Si empeora:
   - rollback de modelo (seccion siguiente).

## Rollback de modelo ML
### Rollback automatico a version previa
```bash
curl -s -X POST http://localhost:8090/v1/ml/rollback \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: admin" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{}'
```

### Rollback a version puntual
```bash
curl -s -X POST http://localhost:8090/v1/ml/rollback \
  -H "Content-Type: application/json" \
  -H "X-SERVICE-KEY: servicekey123" \
  -H "X-USER-ID: admin" \
  -H "X-PROJECT-ID: demo-project" \
  -d '{"target_version":"v1_20260201_090000"}'
```

## Recompute masivo controlado
1. Encolar por eventos:
   - `POST /v1/jobs/recompute-queue/enqueue`
2. Procesar en lotes:
   - `POST /v1/jobs/recompute-queue/process`
3. Verificar counters:
   - `claimed`, `processed`, `ok`, `locked`, `errors`.

## Recovery checklist
1. Salud/ready en verde.
2. Insights compute funcionando (`POST /v1/insights/compute`).
3. ML status consistente (`has_active_model=true` si aplica).
4. Metricas estables por 15-30 minutos.
