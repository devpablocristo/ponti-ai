# Cómo probar Insights - Paso a paso

## Opción A: Con datos de prueba (sin Ponti completo)

### 1. Levantar servicios

```bash
make up
make migrate
```

Si `make migrate` falla por "Dirty database", ejecuta las migraciones faltantes manualmente:

```bash
docker compose exec -T ai-db psql -U postgres -d ai_copilot < migrations/000031_ai_baselines_window_name.up.sql
docker compose exec -T ai-db psql -U postgres -d ai_copilot < migrations/000032_ai_insights_columns.up.sql
docker compose exec -T ai-db psql -U postgres -d ai_copilot < migrations/000060_ai_ml_model_registry.up.sql
```

### 2. Verificar que DB_DSN apunte a ai_copilot

En `docker-compose.yml`, el servicio `ai-copilot` debe usar:

```yaml
- DB_DSN=postgresql://postgres:postgres@ai-db:5432/ai_copilot?sslmode=disable
```

Si usas `new_ponti_db_dev`, cámbialo temporalmente para pruebas. Luego:

```bash
docker compose up -d ai-copilot
```

### 2.1 (Opcional) Habilitar LLM/embeddings reales en local

Si querés probar propuestas (planner LLM) y RAG con embeddings reales, usá Ollama.

```bash
docker compose up -d ollama
make pull-ollama-models
```

Y en `docker-compose.yml` (servicio `ai-copilot`) confirmá:
- `LLM_PROVIDER=ollama`
- `LLM_BASE_URL=http://ollama:11434`
- `LLM_MODEL=llama3.1`
- `EMBEDDING_PROVIDER=ollama`
- `EMBEDDING_MODEL=nomic-embed-text`

Si no querés depender de Ollama, dejá `LLM_PROVIDER=stub` y `EMBEDDING_PROVIDER=stub`.

### 3. Ejecutar el seed de datos de prueba

```bash
docker compose exec -T ai-db psql -U postgres -d ai_copilot < scripts/seed_insights_test_data.sql
```

O desde el host (con psql):

```bash
psql "postgresql://postgres:postgres@localhost:55432/ai_copilot?sslmode=disable" -f scripts/seed_insights_test_data.sql
```

### 4. Probar en Postman (o curl)

**Headers en todas las requests:**
- `X-SERVICE-KEY: servicekey123`
- `X-USER-ID: 123`
- `X-PROJECT-ID: 1`  ← **Importante: usar `1` (proyecto del seed)**

**Orden de requests:**

1. **Recomputar baselines**
   ```
   POST /v1/jobs/recompute-baselines
   Body: {"batch_size": 200}
   ```

2. **Computar insights**
   ```
   POST /v1/insights/compute
   ```

3. **Ver resumen**
   ```
   GET /v1/insights/summary
   ```

4. **Ver insights del proyecto**
   ```
   GET /v1/insights/project/1
   ```

5. **Explicar un insight** (usa un `id` del paso 3 o 4)
   ```
   GET /v1/copilot/insights/{insight_id}/explain
   GET /v1/copilot/insights/{insight_id}/why
   GET /v1/copilot/insights/{insight_id}/next-steps
   ```

6. **Registrar acción**
   ```
   POST /v1/insights/{insight_id}/actions
   Body: {"action": "acknowledged", "new_status": "acknowledged"}
   ```

### 5.1 (Opcional) Probar ML de verdad en Option A

1. Asegurate de tener `ML_ENABLED=true` en `docker-compose.yml` para el servicio `ai-copilot`.
2. Entrenar y activar un modelo:
   ```bash
   make train-ml
   ```
3. Repetí `POST /v1/insights/compute` y verificá en respuesta/audit que aparezcan insights ML (`ml_insights_created > 0`).

---

## Opción B: Con Ponti real (new_ponti_db_dev)

Si tienes la base Ponti con datos:

1. Deja `DB_DSN` apuntando a `new_ponti_db_dev` en docker-compose.
2. Usa un `X-PROJECT-ID` que exista en tu base (ej: `123`).
3. Sigue los pasos 4–6 de la Opción A.

---

## Variables de Postman

En la colección, configura:
- `project_id`: `1` (para seed) o tu project_id real
- `insight_id`: un UUID devuelto por summary o get insights
