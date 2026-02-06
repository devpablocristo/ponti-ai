# Ponti-AI / AI Copilot v2 - Arquitectura Actualizada

## 1) Que es este servicio
Ponti-AI es una API en FastAPI que:
- calcula insights (alertas/anomalias de negocio) por `project_id`
- persiste insights y acciones
- genera propuestas operativas con LLM (auditables)
- expone explainability de insights
- combina deteccion por reglas + ML (Isolation Forest) en el flujo de compute

`Read-only` aplica a datos de negocio core. El servicio escribe sus propias tablas tecnicas.

## 2) Tablas que escribe el servicio
- `ai_insights`
- `ai_insight_actions`
- `ai_insight_proposals`
- `ai_audit_logs`
- `ai_baselines`
- `ai_rag_documents`
- `ai_rag_chunks`
- `ai_rag_embeddings`
- `ai_ml_models`

Migraciones relevantes:
- `migrations/000020_ai_insights.up.sql`
- `migrations/000050_ai_insight_proposals.up.sql`
- `migrations/000010_ai_tables.up.sql`
- `migrations/000030_ai_baselines.up.sql`
- `migrations/000060_ai_ml_model_registry.up.sql`

## 3) Arquitectura (hexagonal liviana)
### 3.1 Composition root
- `app/main.py`
- Instancia adapters de DB/LLM/RAG/ML
- Construye use cases
- Carga todo en `AppContainer`

### 3.2 Inbound adapters
- `adapters/inbound/api/routes/*.py`
- `adapters/inbound/api/schemas/*.py`
- `adapters/inbound/api/auth/headers.py`

### 3.3 Application
- `application/*/use_cases/*.py`
- `application/*/ports/*.py` (interfaces tipo Go con `Protocol`)

### 3.4 Domain
- `domain/*/entities.py` (dataclasses inmutables)

### 3.5 Bounded context ML
- `ml/` con su propia mini-hexagonal
- `ml/facade.py` expone `train()` y `detect_anomalies()`

## 4) Seguridad de entrada
Headers obligatorios en endpoints de negocio:
- `X-SERVICE-KEY`
- `X-USER-ID`
- `X-PROJECT-ID`

Validacion:
- `adapters/inbound/api/auth/headers.py`
- `adapters/outbound/security/api_keys.py`

## 5) Endpoints actuales
### 5.1 Salud
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `GET /v1/ml/status`
- `POST /v1/ml/activate`
- `POST /v1/ml/rollback`

### 5.2 Insights
- `POST /v1/insights/compute`
- `GET /v1/insights/{entity_type}/{entity_id}`
- `GET /v1/insights/summary`
- `POST /v1/insights/{insight_id}/actions`

### 5.3 Copilot (explainability)
- `GET /v1/copilot/insights/{insight_id}/explain`
- `GET /v1/copilot/insights/{insight_id}/why`
- `GET /v1/copilot/insights/{insight_id}/next-steps`
- `POST /v1/rag/ingest`

### 5.4 Jobs
- `POST /v1/jobs/recompute-active`
- `POST /v1/jobs/recompute-baselines`
- `POST /v1/jobs/retrain-ml`
- `POST /v1/jobs/retrain-ml-if-needed`

## 6) Flujo punta a punta de insights (real)
Ejemplo: proyecto `finca-san-jose` reporta costos elevados.

### Paso 1: Request
Cliente llama `POST /v1/insights/compute` con headers de auth.
Router: `adapters/inbound/api/routes/insights.py`.

### Paso 2: Orquestacion del use case
`ComputeInsights.handle(project_id, user_id)`:
1. `feature_repo.fetch_features(project_id)`
2. `model_runner.compute(project_id, features)` (reglas)
3. si hay `ml_detector`, `detect_anomalies(project_id, features)` y merge
4. dedupe por `dedupe_key` + `cooldown_until`
5. `insight_repo.upsert_many(filtered)`
6. planner LLM por insight (gating)
7. audit log final

Archivo: `application/insights/use_cases/compute_insights.py`.

### Paso 3: Feature extraction
`FeatureRepositoryPG.fetch_features()`:
- recorre catalogo de SQL allowlisted
- valida params
- ejecuta con timeout y limit
- transforma filas a `FeatureValue`

Archivos:
- `adapters/outbound/db/repos/feature_repo_pg.py`
- `adapters/outbound/sql/catalog.py`
- `adapters/outbound/sql/executor.py`
- `adapters/outbound/sql/validators.py`

### Paso 4: Deteccion por reglas
`AnomalyRunner.compute()`:
- arma `cohort_key` por `total_hectares`
- busca baseline `self` -> `cohort` -> fallback `window=all`
- si `value >= p90`: `type=anomaly`, `severity=80`
- si `value >= p75`: `type=recommendation`, `severity=40`
- detecta spikes (`last_7d` vs `last_30d`)

Archivo: `adapters/outbound/models/anomaly_runner.py`.

### Paso 5: Deteccion por ML
`MLFacade.detect_anomalies()`:
- verifica ML habilitado
- verifica modelo activo
- aplica rollout por proyecto (`ML_ROLLOUT_PERCENT` + allowlist opcional)
- calcula drift score por request (solo observabilidad)
- convierte features a `Dataset`
- carga modelo/pipeline activos (lazy)
- predice anomaly score
- mapea score a `Insight` si cruza threshold
- si `ML_SHADOW_MODE=true`, persiste insight ML como `status=shadow`

Archivos:
- `ml/facade.py`
- `ml/application/use_cases/predict_anomaly.py`
- `ml/adapters/training/filesystem_model_store.py`

### Paso 6: Dedupe/cooldown
Antes de persistir, `ComputeInsights` descarta insights que:
- tienen mismo `dedupe_key`
- y ya existe insight activo en cooldown

Repositorio:
- `adapters/outbound/db/repos/insight_repo_pg.py`

### Paso 7: Persistencia
`upsert_many()` en `ai_insights` con `ON CONFLICT (id) DO UPDATE`.

### Paso 8: Planner LLM (propuesta)
`_maybe_generate_proposal()` corre solo si:
- `status == new`
- `severity >= 70`
- `evidence.n_samples >= 30`
- no existe proposal `status=ok` previa

Proceso:
- arma contexto historico (`ai_insights` + `ai_insight_actions`)
- llama `InsightPlannerLLM.plan()`
- valida JSON con Pydantic
- valida tools/args contra catalogo
- persiste en `ai_insight_proposals`
- fail-open si LLM falla

Archivos:
- `application/insights/use_cases/compute_insights.py`
- `adapters/outbound/llm/insight_planner.py`
- `adapters/outbound/tools/catalog.py`
- `adapters/outbound/db/repos/proposal_store_pg.py`

### Paso 9: Auditoria
Siempre registra `ai_audit_logs` (ok/error) con tiempos y conteos.

Archivo:
- `adapters/outbound/db/repos/audit_logger_pg.py`

### Paso 10: Respuesta API
`POST /v1/insights/compute` retorna:
- `request_id`
- `computed`
- `insights_created`

Internamente tambien computa:
- `rules_insights_created`
- `ml_insights_created`

## 7) Explainability
### 7.1 Explain insight
`ExplainInsight.handle(project_id, insight_id, mode)`:
- busca insight
- busca ultima propuesta `ok`
- llama `CopilotExplainerLLM`
- retorna `explanation + proposal`

Archivos:
- `application/copilot/use_cases/explain_insight.py`
- `adapters/outbound/llm/copilot_explainer.py`

### 7.2 Nota
Copilot v2 no expone chat libre: la capa de explainability funciona por `insight_id` via endpoints `/v1/copilot/...`.

## 8) Jobs y locks
### Recompute active
- `POST /v1/jobs/recompute-active`
- lock advisory en PG (`pg_try_advisory_lock`)
- recomputa insights y marca recomputed

### Recompute baselines
- `POST /v1/jobs/recompute-baselines`
- lock advisory en PG
- recalcula baselines de cohorte y proyecto

### Retrain ML
- `POST /v1/jobs/retrain-ml`
- lock advisory en PG dedicado (`ML_RETRAIN_LOCK_KEY`)
- entrena modelo via `MLFacade.retrain_with_policy(...)`
- permite `version`, `activate` (forzado), `auto_promote`, `hyperparameters`
- retorna `status`, `job_run_id`, `model_version`, `training_time_seconds`, `metrics`

### Retrain ML automatico
- `POST /v1/jobs/retrain-ml-if-needed`
- saltea entrenamiento si el modelo activo es mas nuevo que `ML_AUTO_RETRAIN_MIN_HOURS`
- si entrena, aplica policy de promotion automaticamente

Archivos:
- `application/insights/use_cases/recompute_active.py`
- `application/insights/use_cases/recompute_baselines.py`
- `adapters/outbound/db/job_lock_pg.py`
- `adapters/inbound/api/routes/jobs.py`

## 9) Operacion ML (actual)
### Entrenamiento
- comando: `python -m ml.scripts.train --activate`
- en Makefile: `make train-ml`
- persiste artefactos en `ML_MODELS_DIR`

### Persistencia de modelos
- estructura: `ml_models/<model_type>/<version>/`
- `active.txt` define version activa
- metadata/versionado/activacion tambien se guardan en `ai_ml_models`
- rollback soportado por API (`/v1/ml/rollback`) usando historial de activaciones

### Runtime
- `app/main.py` crea `ml_facade` si `ML_ENABLED=true`
- `ComputeInsights` lo usa como `ml_detector`
- si ML falla, el flujo sigue con reglas (fail-open)
- `GET /v1/ml/status` expone estado operativo del modulo ML
- `POST /v1/ml/activate` cambia version activa en caliente
- `POST /v1/ml/rollback` vuelve a version anterior o especifica
- policy de promotion configurable con `ML_AUTO_PROMOTE` + thresholds de mejora

## 10) Observabilidad
`/metrics` expone counters/timers in-memory.

Métricas clave:
- `insights.compute.count`
- `insights.compute.duration_ms`
- `insights.compute.rules_created`
- `insights.compute.ml_created`
- `ml.drift.low.count`
- `ml.drift.medium.count`
- `ml.drift.high.count`
- `ml.rollout.skipped.count`
- `insights.compute.ml_shadow.count`

## 11) Checklist minimo de produccion
- Migraciones aplicadas incluyendo `000060_ai_ml_model_registry.up.sql`.
- `ML_ENABLED=true` solo cuando ya existe una version entrenada y activa.
- `ML_ROLLOUT_PERCENT` iniciar en 5-10 y subir gradualmente con monitoreo.
- Alertas operativas sobre `/metrics` para drift alto y errores de planner.
- Runbook de rollback validado (`POST /v1/ml/rollback`) y probado en staging.
- Reentrenamiento periodico programado (`POST /v1/jobs/retrain-ml` o scheduler externo).

## 12) TODO acordado
- Observabilidad operativa avanzada (Prometheus/Grafana/Datadog con alertas SLO) queda en TODO.
- Runbook operativo de incidentes (on-call, degradacion, rollback, recovery) queda en TODO.
- Objetivo: mantener estos 2 items fuera de este ciclo de implementacion.

## 13) Traduccion para dev Go
- `@dataclass(frozen=True)` ~= `struct` inmutable
- `Protocol` ~= interfaz por contrato de metodos
- `Depends(...)` ~= inyeccion por request en handler
- Pydantic ~= struct + validacion de payload
- `with` en Python ~= `defer`/scope-safe resource handling

## 14) Estado de madurez (honesto)
### Ya productivo en lo base
- API estable de insights/coplas
- persistencia robusta
- dedupe/cooldown
- jobs con lock
- ML integrado al compute

### Aun MVP/stub
- RAG embeddings usa stub deterministico (`adapters/outbound/rag/embeddings.py`)
- el registry de modelos ya es DB + filesystem, pero sin almacenamiento remoto de artefactos
- faltan alertas externas y tableros operativos formales (pendiente en TODO de observabilidad)
- faltan SLO/alertas externas (Prometheus/Datadog) y dashboard operativo formal

## 15) Ejemplo real de flujo operativo
1. `make up`
2. `make train-ml`
3. `POST /v1/insights/compute`
4. `GET /v1/insights/summary`
5. tomar un `insight_id`
6. `GET /v1/copilot/insights/{insight_id}/explain`
7. `POST /v1/insights/{insight_id}/actions`
8. observar `/metrics` (`ml_created` vs `rules_created`)

## 16) Operacion recomendada diaria
1. Consultar `GET /v1/ml/status` antes de ventanas operativas.
2. Validar que `has_active_model=true`.
3. Si hace falta refrescar modelo, ejecutar `POST /v1/jobs/retrain-ml`.
4. Verificar `metrics` y `model_version` de la respuesta.
5. Ejecutar `POST /v1/insights/compute` y observar `/metrics` con foco en `insights.compute.rules_created` vs `insights.compute.ml_created`.
