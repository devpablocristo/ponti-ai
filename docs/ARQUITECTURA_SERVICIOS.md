# Descripción Completa de los Servicios - AI Copilot (Ponti)

**TLDR:** Servicio FastAPI read-only con arquitectura hexagonal que expone (1) **Insights v2** como sensor + disparador operativo (propuestas vía LLM persistidas y auditables) y (2) **Copilot v2** como capa de explainability (no chat libre). PostgreSQL + pgvector para RAG.

---

## 1. Visión General

El **AI Copilot Service** es un backend de IA que actúa como capa intermedia entre el frontend (BFF) y los datos de negocio. Se integra en el flujo:

```
FE (UI) → BFF (ponti-frontend/api, valida JWT) → Backend Go (proxy seguro) → AI Service (FastAPI, READ-ONLY)
```

**Características principales:**
- **Insights v2 (sensor + propuesta)**: detecta desvíos vs baselines y, si pasa gating determinístico, llama a un LLM planner que genera una **propuesta operativa estructurada** y la persiste (audit/dedupe/repro)
- **Copilot v2 (explainability)**: explica un insight existente y su propuesta (si existe); no explora datos ni genera propuestas
- **RAG**: ingestión y búsqueda semántica de documentos por proyecto
- **Jobs asíncronos**: recomputación de insights activos y baselines (para Cloud Scheduler)

---

## 2. Arquitectura Hexagonal

```
domain/           → Entidades y value objects
application/      → Use cases + ports (interfaces)
adapters/
  inbound/api/    → FastAPI, schemas, auth
  outbound/       → DB, SQL, RAG, modelos, observabilidad
app/main.py       → Wiring manual (sin DI framework)
```

- **Adapters** usan DTOs para comunicación externa
- **Use cases** trabajan con primitivos o tipos de dominio
- **Repositories** usan modelos del package models

---

## 3. API REST - Endpoints

### 3.1 Headers Requeridos

Todos los endpoints (excepto health/metrics) exigen:

| Header        | Descripción                          |
|---------------|--------------------------------------|
| `X-SERVICE-KEY` | API key (validada contra `AI_SERVICE_KEYS`) |
| `X-USER-ID`     | Identificador del usuario            |
| `X-PROJECT-ID`  | Identificador del proyecto           |

Las keys se configuran en `.env` como lista separada por comas: `AI_SERVICE_KEYS=key1,key2`.

---

### 3.2 Health y Observabilidad

| Método | Ruta       | Descripción                                      |
|--------|------------|--------------------------------------------------|
| GET    | `/healthz` | Liveness: responde `{"status":"ok"}`             |
| GET    | `/readyz`  | Readiness: verifica conexión a DB                |
| GET    | `/metrics` | Snapshot de métricas (contadores, histogramas)   |

---

### 3.3 Copilot

#### `POST /v1/ask`

Endpoint mantenido por compatibilidad, pero **deprecado** como chat libre. En v2 actúa como wrapper de explainability:
- Si el `question` contiene un `insight_id` (UUID) → devuelve explicación.
- Si no contiene `insight_id` → devuelve respuesta determinística indicando que no hay chat libre.

**Request:**
```json
{
  "question": "Necesito el resumen del proyecto",
  "context": {
    "date_from": "2025-01-01",
    "date_to": "2025-12-31"
  }
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "intent": "metrics|docs|analysis",
  "query_id": "project_overview",
  "params": { "project_id": "...", "date_from": "...", "date_to": "..." },
  "data": [ { ... } ],
  "answer": "Consulta ejecutada correctamente.",
  "sources": [ { "type": "sql", "query_id": "...", "params": {...} ],
  "warnings": [],
  "related_insights_count": 5,
  "related_insights": [
    { "id": "...", "entity_type": "project", "entity_id": "...", "title": "..." }
  ]
}
```

**Flujo interno (v2):**
1. Extracción de `insight_id` desde el texto
2. Lectura de `ai_insights` + propuesta persistida (si existe)
3. LLM explainability (sin crear estado nuevo)
4. Auditoría en `ai_audit_logs`
5. Inclusión de top 3 insights activos relacionados

#### Endpoints Copilot v2 (explainability)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/v1/copilot/insights/{insight_id}/explain` | Explicación completa (humana + audit + qué mirar) |
| GET | `/v1/copilot/insights/{insight_id}/why` | Enfocado en causa probable / por qué importa |
| GET | `/v1/copilot/insights/{insight_id}/next-steps` | Enfocado en próximos pasos sugeridos (desde propuesta existente) |

---

#### `POST /v1/rag/ingest`

Ingesta documentos para RAG por proyecto.

**Request:**
```json
{
  "documents": [
    {
      "source": "manual",
      "title": "Guía de uso",
      "content": "Contenido del documento...",
      "metadata": {}
    }
  ]
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "ingested": 3
}
```

`ingested` = número de chunks creados (cada documento se divide en chunks de 1000 caracteres con overlap 100).

---

### 3.4 Insights

#### `POST /v1/insights/compute`

Calcula insights para el proyecto actual (on-demand).

**Response:**
```json
{
  "request_id": "uuid",
  "computed": 15,
  "insights_created": 3
}
```

- `computed`: features evaluadas
- `insights_created`: insights nuevos/actualizados tras deduplicación y cooldown

#### Insights v2: análisis LLM + propuesta persistida

Después del compute, cada insight pasa por un **gating determinístico (antes del LLM)**:
- `severity >= 70`
- `n_samples >= 30` (desde `evidence.n_samples`)
- `status = "new"`
- no existe propuesta previa `status="ok"` para ese `insight_id`

Si pasa el gating:
- se llama al LLM planner (prompt versionado)
- se valida salida por schema + tool catalog
- se persiste en `ai_insight_proposals` (`status=ok|error`)

Si el LLM falla:
- el insight se guarda igual
- la propuesta queda `status="error"` con `error_message`
- el flujo de insights no se rompe

---

#### `GET /v1/insights/{entity_type}/{entity_id}`

Lista insights de una entidad (ej. `project` / `123`).

**Response:**
```json
{
  "insights": [
    {
      "id": "...",
      "project_id": "...",
      "entity_type": "project",
      "entity_id": "...",
      "type": "anomaly|recommendation|spike",
      "severity": 80,
      "priority": 80,
      "title": "cost_total alto vs baseline",
      "summary": "...",
      "evidence": { "feature": "...", "p75": ..., "p90": ... },
      "explanations": { "rule": "baseline_percentile" },
      "action": {
        "action_type": "review_inputs",
        "action_params": { "feature": "cost_total", "window": "all" },
        "suggested_due_date": "2026-02-07",
        "cta_label": "Revisar costos"
      },
      "impact_min": 0.35,
      "impact_max": 0.65,
      "impact_unit": "%",
      "confidence": "high|medium|low",
      "dedupe_key": "...",
      "cooldown_until": "...",
      "computed_at": "...",
      "valid_until": "...",
      "status": "new|acknowledged|..."
    }
  ]
}
```

---

#### `GET /v1/insights/summary`

Resumen para badges/notificaciones.

**Response:**
```json
{
  "new_count_total": 5,
  "new_count_high_severity": 2,
  "top_insights": [ ... ]
}
```

- `new_count_total`: insights con `status=new` y `valid_until >= now`
- `new_count_high_severity`: mismos con `severity >= 80`
- `top_insights`: top 3 por severidad y fecha

---

#### `POST /v1/insights/{insight_id}/actions`

Registra acción del usuario sobre un insight.

**Request:**
```json
{
  "action": "acknowledged",
  "new_status": "acknowledged"
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "status": "ok"
}
```

Inserta en `ai_insight_actions` y actualiza `status` del insight.

---

### 3.5 Jobs (Cloud Scheduler)

#### `POST /v1/jobs/recompute-active`

Recomputa insights activos del proyecto. Usa lock para evitar ejecuciones concurrentes.

**Request (opcional):**
```json
{ "batch_size": 100 }
```

**Response:**
```json
{
  "status": "ok|locked",
  "job_run_id": "uuid"
}
```

Si `locked`, otro proceso tiene el lock (`INSIGHTS_RECOMPUTE_LOCK_KEY`).

---

#### `POST /v1/jobs/recompute-baselines`

Recomputa baselines de cohorte y por proyecto.

**Request (opcional):**
```json
{ "batch_size": 200 }
```

**Response:**
```json
{
  "status": "ok|locked",
  "job_run_id": "uuid",
  "cohort_saved": 42,
  "project_saved": 150
}
```

- `cohort_saved`: baselines por cohorte (size=small|medium|large)
- `project_saved`: baselines por proyecto (historial propio)

---

## 4. Componentes de IA

### 4.1 Clasificador de Intención (`IntentClassifier`)

**Ubicación:** `adapters/outbound/models/intent_classifier.py`

**Función:** Determina si la pregunta es sobre documentación (`docs`), métricas (`metrics`) o análisis (`analysis`).

**Implementación actual (stub):**
- Si la pregunta contiene "documento", "manual", "guia", "readme", "doc" → `intent=docs`
- En otro caso, clasificación por keywords:
  - "costo por hectarea", "costo/ha" → `cost_per_ha`
  - "hectarea" → `total_hectares`
  - "lote" → `total_hectares_by_lot`
  - "insumo" + "categoria" → `inputs_by_category`
  - "insumo" → `inputs_total_used`
  - "orden" + "30/mes/ultimos" → `workorders_last_30d`
  - "orden" → `workorders_count`
  - "stock" → `stock_variance`
  - "campaña/indicador" → `operational_indicators`
  - "costo" → `project_overview`
- Por defecto: `project_overview`

**Salida:** `IntentDecision(intent, query_id, params)`.

---

### 4.2 RAG (Retrieval-Augmented Generation)

**Ubicación:** `adapters/outbound/rag/`

**Pipeline:**

1. **Ingest** (`ingest.py`):
   - Documento → chunks (1000 chars, overlap 100)
   - Cada chunk → embedding (actualmente stub determinístico por texto)
   - Inserta en `ai_rag_documents`, `ai_rag_chunks`, `ai_rag_embeddings`

2. **Search** (`search.py`):
   - Pregunta → embedding
   - Búsqueda por similitud coseno en pgvector (`<->`)
   - Devuelve `doc_ids` y respuesta genérica (MVP: texto fijo)

3. **Embeddings** (`embeddings.py`):
   - Stub: `random.Random(seed)` con `seed = sum(ord(c) for c in text)`
   - Producción: reemplazar por modelo real (OpenAI, etc.)

4. **Chunking** (`chunking.py`):
   - `chunk_size=1000`, `overlap=100`

---

### 4.3 Motor de Anomalías (`AnomalyRunner`)

**Ubicación:** `adapters/outbound/models/anomaly_runner.py`

**Función:** Genera insights comparando features del proyecto contra baselines.

**Reglas:**

1. **Baseline percentil (p75/p90):**
   - `value >= p90` → `anomaly`, severity 80
   - `value >= p75` → `recommendation`, severity 40
   - `value < p75` → no insight

2. **Spike (7d vs 30d):**
   - Features: `cost_total`, `inputs_total_used`, `workorders_count`
   - `ratio = last_7d / (last_30d / 4)`
   - Si `ratio >= INSIGHTS_SPIKE_RATIO` → `spike`, severity 90

3. **Jerarquía de baselines:**
   - Primero: baseline propio del proyecto (`scope_type=project`, `cohort_key=self`)
   - Si no existe: baseline de cohorte (`scope_type=global`, `cohort_key=size=small|medium|large`)
   - Si no existe: baseline de cohorte con `window=all`

4. **Cohorte por tamaño:**
   - `total_hectares <= size_small_max` → `size=small`
   - `total_hectares <= size_medium_max` → `size=medium`
   - Si no → `size=large`

5. **Deduplicación y cooldown:**
   - `dedupe_key`: `{feature}:{window}:{type}` o `{feature}:spike`
   - Si ya existe insight activo con mismo `dedupe_key` y `cooldown_until > now` → no crear

6. **Impacto y confianza:**
   - `impact_pct = min(max(delta_ratio * impact_k, 0), impact_cap)`
   - `confidence`: high (n≥50), medium (n≥20), low (resto)

7. **Acciones sugeridas:**
   - `inputs_total_used`, `stock_variance` → `inventory_check`, "Revisar stock"
   - `cost_total`, `cost_per_ha` → `review_inputs`, "Revisar costos"
   - Resto → `checklist`, "Revisar"

---

## 5. Catálogo SQL

**Ubicación:** `adapters/outbound/sql/catalog.py`

### 5.1 Copilot (consultas conversacionales)

| query_id               | Descripción                          |
|------------------------|--------------------------------------|
| `project_overview`     | Costos directos ejecutados           |
| `cost_per_ha`         | Costo por hectárea                   |
| `inputs_by_category`  | Insumos por categoría (USD)          |
| `inputs_total_used`   | Uso total de insumos                 |
| `workorders_count`    | Cantidad de órdenes de trabajo       |
| `workorders_last_30d` | Órdenes últimos 30 días              |
| `stock_variance`      | Diferencia stock real vs inicial     |
| `total_hectares`      | Hectáreas totales                    |
| `total_hectares_by_lot` | Hectáreas por lote                 |
| `operational_indicators` | Indicadores operativos campaña    |

### 5.2 Features (para insights)

Features con ventanas `all`, `last_30d`, `last_7d` para:
- `cost_total`, `cost_per_ha`, `inputs_total_used`, `workorders_count`, `stock_variance`, `total_hectares`

### 5.3 Baselines

- **Cohorte** (`baseline_catalog.py`): percentiles p50/p75/p90 por `cohort_key` (size=small|medium|large) para cada feature/window
- **Proyecto**: percentiles del historial del proyecto (`baseline_days` días)

---

## 6. Base de Datos

### 6.1 Tablas Principales

| Tabla               | Uso                                      |
|---------------------|------------------------------------------|
| `ai_rag_documents`  | Documentos RAG por proyecto              |
| `ai_rag_chunks`     | Chunks de documentos                     |
| `ai_rag_embeddings` | Embeddings (vector 1536) por chunk       |
| `ai_audit_logs`     | Auditoría de requests del Copilot       |
| `ai_insights`       | Insights generados                       |
| `ai_insight_actions`| Acciones de usuario sobre insights       |
| `ai_baselines`      | Baselines (scope_type, scope_id, cohort_key, feature_name, window, p50/p75/p90, n_samples) |

### 6.2 Índices Relevantes

- `ai_rag_embeddings`: búsqueda por `project_id` + vector
- `ai_insights`: `(project_id, status, valid_until)`, `(project_id, entity_type, entity_id, computed_at)`
- `ai_baselines`: `(scope_type, scope_id, cohort_key, feature_name, window)`

### 6.3 Locks

- `pg_try_advisory_lock(key)` para jobs:
  - `INSIGHTS_BASELINE_LOCK_KEY` (41001): recompute-baselines
  - `INSIGHTS_RECOMPUTE_LOCK_KEY` (41002): recompute-active

---

## 7. Configuración (.env)

| Variable                      | Descripción                              |
|------------------------------|------------------------------------------|
| `APP_NAME`, `APP_ENV`        | Identificación del servicio              |
| `DB_DSN`                     | Conexión PostgreSQL                      |
| `AI_SERVICE_KEYS`            | API keys separadas por coma              |
| `STATEMENT_TIMEOUT_MS`       | Timeout por query SQL                    |
| `MAX_LIMIT`, `DEFAULT_LIMIT` | Límites de paginación                    |
| `EMBEDDING_DIM`              | Dimensión de vectores (1536)             |
| `RAG_TOP_K`                  | Documentos top-K en búsqueda RAG         |
| `LLM_PROVIDER`               | Proveedor LLM (stub/real)                |
| `INSIGHTS_RATIO_HIGH`        | Ratio para severidad alta                |
| `INSIGHTS_RATIO_MEDIUM`      | Ratio para severidad media               |
| `INSIGHTS_SPIKE_RATIO`       | Ratio 7d/30d para spike                  |
| `INSIGHTS_COOLDOWN_DAYS`     | Días de cooldown por insight             |
| `INSIGHTS_IMPACT_K`, `INSIGHTS_IMPACT_CAP` | Cálculo de impacto               |
| `INSIGHTS_SIZE_SMALL_MAX`    | Máx. hectáreas para cohorte small        |
| `INSIGHTS_SIZE_MEDIUM_MAX`   | Máx. hectáreas para cohorte medium       |
| `INSIGHTS_PROJECT_BASELINE_DAYS` | Días de historial para baseline propio |
| `INSIGHTS_MIN_SAMPLES_PROJECT`   | Mín. muestras para baseline proyecto  |
| `INSIGHTS_BASELINE_LOCK_KEY`     | Lock recompute baselines              |
| `INSIGHTS_RECOMPUTE_LOCK_KEY`    | Lock recompute insights               |
| `INSIGHTS_BASELINE_BATCH_SIZE`   | Tamaño de batch para proyectos       |

---

## 8. Flujos de Datos

### 8.1 Ask Copilot

```
Request → require_headers → AskCopilot.handle()
  → IntentClassifier.classify()
  → [docs] RagRepository.search() → RagSearchResult
  → [metrics] SQLCatalog.get_entry() → SQLExecutor.execute() → data
  → AuditLogger.log()
  → InsightReader.count_active(), list_active()
  → AskResponse
```

### 8.2 Compute Insights

```
Request → ComputeInsights.handle()
  → FeatureRepository.fetch_features() → list[FeatureValue]
  → AnomalyRunner.compute() → list[Insight]
  → dedupe + cooldown filter
  → InsightRepository.upsert_many()
  → AuditLogger.log()
```

### 8.3 Recompute Baselines

```
Request → RecomputeBaselines.handle()
  → JobLock.try_lock()
  → BaselineComputer.compute_cohort_baselines() → list[BaselineRecord]
  → BaselineRepository.upsert_many()
  → ProjectRepository.list_project_ids() (batch)
  → BaselineComputer.compute_project_baselines() por proyecto
  → BaselineRepository.upsert_many()
  → JobLock.release()
```

---

## 9. Puertos (Interfaces)

### Copilot
- `IntentClassifierPort`: clasificar pregunta → IntentDecision
- `SQLCatalogPort`: obtener entrada por query_id
- `SQLExecutorPort`: ejecutar SQL con params
- `RagRepositoryPort`: ingest, search
- `AuditLoggerPort`: log de requests
- `InsightReaderPort`: count_active, list_active

### Insights
- `FeatureRepositoryPort`: fetch_features
- `ModelRunnerPort`: compute(project_id, features) → list[Insight]
- `InsightRepositoryPort`: upsert_many, get_by_entity, get_summary, record_action, get_active_by_dedupe
- `BaselineRepositoryPort`: get_baseline, upsert_many
- `BaselineComputerPort`: compute_cohort_baselines, compute_project_baselines
- `ProjectRepositoryPort`: list_project_ids
- `JobLockPort`: try_lock, release

---

## 10. Observabilidad

- **Métricas:** `inc_counter`, `observe_ms` (duración)
- **Eventos:** `log_event` con payload JSON
- **Métricas expuestas:** `GET /metrics` → snapshot de contadores e histogramas

---

## 11. Dependencias Externas

- **PostgreSQL** con extensión **pgvector**
- **Vistas/schemas** del backend principal: `v4_report.*`, `v4_ssot.*`, `public.*`
- Funciones como `v4_ssot.total_hectares_for_project(project_id)`

---

*Documento generado para comprensión completa del AI Copilot Service.*
