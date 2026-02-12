# Observabilidad y SLOs

## Fuentes de observabilidad
- Endpoint `GET /metrics` (counters y timers in-memory).
- Logs estructurados (`adapters/outbound/observability/logging.py`).
- Estado ML (`GET /v1/ml/status`).

## SLOs operativos recomendados
1. Disponibilidad API:
   - SLO: `99.9%` de respuestas exitosas en `/healthz` y `/readyz`.
2. Latencia compute:
   - SLO: p95 de `insights.compute.duration_ms` menor a `2000ms`.
3. Error budget planner:
   - SLO: fallos LLM no afectan disponibilidad de compute (fail-open).
4. Sanidad ML:
   - SLO: `has_active_model=true` en horarios de operación.

## Alertas mínimas recomendadas
1. `readyz` degradado:
   - trigger: `readyz != ok` por 3 checks consecutivos.
2. Latencia anómala:
   - trigger: `insights.compute.duration_ms.avg_ms` supera umbral acordado.
3. Drift ML alto:
   - trigger: incremento de `ml.drift.high.count`.
4. Cola de recompute con errores:
   - trigger: `errors > 0` persistente en `recompute-queue/process`.
5. Rollout saltado excesivo:
   - trigger: aumento sostenido de `ml.rollout.skipped.count`.

## Dashboard base (campos)
1. Throughput:
   - `insights.compute.count`
   - `insights.summary.count`
2. Latencia:
   - `insights.compute.duration_ms.avg_ms`
   - `insights.compute.duration_ms.max_ms`
3. Calidad ML:
   - `insights.compute.ml_created`
   - `insights.compute.rules_created`
   - `ml.drift.low|medium|high.count`
4. Jobs:
   - `jobs.recompute.count`
   - `jobs.baselines.count`
   - `jobs.retrain_ml.count`
   - `jobs.retrain_ml_if_needed.count`

## Instrumentacion externa (sugerida)
- Si se integra Prometheus/Grafana o Datadog:
  - scrapear `/metrics`.
  - mapear counters/timers a series con etiquetas de entorno/servicio.
  - mantener misma nomenclatura para no romper runbooks.
