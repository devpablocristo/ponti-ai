# AI Copilot Service (MVP)

Servicio FastAPI para calcular insights determinísticos y ofrecer explainability acotada por insight.

## Endpoints

Siempre:
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`

Insights:
- `POST /v1/insights/compute`
- `GET /v1/insights/summary`
- `GET /v1/insights/{entity_type}/{entity_id}`
- `POST /v1/insights/{insight_id}/actions`

Copilot (si `COPILOT_ENABLED=true`):
- `GET /v1/copilot/insights/{insight_id}/explain`
- `GET /v1/copilot/insights/{insight_id}/why`
- `GET /v1/copilot/insights/{insight_id}/next-steps`

## Módulos removidos del MVP
- RAG
- ML
- Jobs/Queue

No existen rutas `/v1/rag/*`, `/v1/ml/*`, `/v1/jobs/*`.

## Quickstart
1. Configurar variables de entorno con `.env.example` o `.env.mvp`.
2. Levantar stack:
```bash
make up
```
3. Ejecutar API local:
```bash
make run
```
4. Probar endpoints:
```bash
make smoke-local
```
