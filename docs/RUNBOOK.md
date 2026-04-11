# Runbook de incidentes — Ponti AI

## 1. Chat no responde (timeout / 5xx)

**Síntomas:** Frontend muestra "Error al enviar el mensaje", streaming se corta.

**Diagnóstico:**
```bash
# Verificar que el servicio está corriendo
curl http://localhost:8100/healthz

# Verificar logs del contenedor
docker logs pymes-ponti-ai-1 --tail 50

# Buscar errores de LLM
docker logs pymes-ponti-ai-1 2>&1 | grep -i "error\|timeout\|llm"
```

**Causas comunes:**
- API key de LLM inválida o expirada → verificar `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`
- Timeout de LLM → verificar `LLM_TIMEOUT_MS` (default 60000)
- DB de ponti-ai caída → verificar conexión PostgreSQL

**Mitigación:**
1. Verificar API keys en env vars del servicio
2. Si es timeout, aumentar `LLM_TIMEOUT_MS` temporalmente
3. Si es DB, verificar que PostgreSQL está corriendo y acepta conexiones

---

## 2. Routing incorrecto (agente equivocado)

**Síntomas:** Usuario pregunta sobre labores pero recibe respuesta genérica. Log `ponti_turn_routing_decision` muestra `routing_target=general`.

**Diagnóstico:**
```bash
# Buscar decisiones de routing recientes
docker logs pymes-ponti-ai-1 2>&1 | grep "ponti_turn_routing_decision"
```

**Campos a verificar:**
- `handler_kind`: debería ser `direct_agent` o `insight_lane`, no `orchestrator` para queries con hint
- `route_hint`: debería coincidir con lo que envía el frontend
- `handoff_valid`: si es handoff, debería ser `true`

**Causas comunes:**
- Frontend no envía `route_hint` → verificar selector de contexto en AIAssistant
- Pipeline de routing no matchea keyword → agregar cue en `_infer_read_route`
- Carry-forward no funciona → verificar dossier.workspace.last_route_hint

---

## 3. Insights no se computan

**Síntomas:** Notificaciones vacías, summary retorna 0.

**Diagnóstico:**
```bash
# Verificar trigger en backend Go
docker logs pymes-ponti-backend-1 2>&1 | grep "ai-trigger"

# Verificar compute en ponti-ai
docker logs pymes-ponti-ai-1 2>&1 | grep "insights.compute"
```

**Causas comunes:**
- Trigger middleware no dispara → verificar que la ruta tiene `project_id` param
- Cooldown activo → el trigger throttlea 300s por proyecto (configurable)
- Semáforo lleno → log dice "semáforo lleno, descartando trigger"
- Datos insuficientes → compute retorna `insights_created=0` (esperado si no hay anomalías)

---

## 4. Notificaciones no aparecen en frontend

**Síntomas:** Se computan insights pero no aparecen en la bandeja de notificaciones.

**Diagnóstico:**
```bash
# Verificar sync en backend Go
docker logs pymes-ponti-backend-1 2>&1 | grep "sincronizando notificaciones"

# Verificar que el summary tiene insights
curl -H "X-USER-ID: user" -H "X-TENANT-ID: project_id" http://localhost:8100/v1/insights/summary
```

**Causas comunes:**
- `SyncFromSummary` falla → verificar log de error
- Insights con ID vacío → se ignoran silenciosamente
- Notification key duplicada → upsert no crea nueva (es idempotente, esperado)
- Frontend no consulta notificaciones → verificar que GET /api/v1/notifications se llama

---

## 5. Handoff notificación → chat falla

**Síntomas:** "Explicar en chat" navega a AIAssistant pero no inicia conversación.

**Diagnóstico:**
1. Verificar que sessionStorage tiene la key `ponti.notificationChatHandoff` antes de navegar
2. Verificar consola del browser para errores
3. Verificar que el proyecto está seleccionado (headers requiere projectId)

**Causas comunes:**
- Proyecto no seleccionado → AIAssistant muestra "Seleccioná un proyecto"
- Handoff JSON malformado → `JSON.parse` falla silenciosamente
- `handoffProcessedRef` ya fue procesado → solo se procesa una vez por mount

---

## 6. Evidence injection no funciona en follow-ups

**Síntomas:** El segundo mensaje sobre un insight no tiene contexto, respuesta genérica.

**Diagnóstico:**
```bash
docker logs pymes-ponti-ai-1 2>&1 | grep "insight_evidence_injected"
```

**Causas comunes:**
- No se guardó `insight_evidence` en el primer turno → verificar que `insight_evidence_payload` no es None
- TTL expirado → evidencia tiene >24h, no se inyecta
- `extract_insight_evidence` no encuentra evidencia → verificar que el assistant_msg del turno 1 tiene el campo

---

## 7. Métricas / observabilidad

**Endpoints útiles:**
- `GET /healthz` — liveness
- `GET /readyz` — readiness
- `GET /metrics` — snapshot de contadores y timers

**Log events clave:**
| Evento | Cuándo | Campos principales |
|--------|--------|-------------------|
| `ponti_turn_routing_decision` | Al resolver ruta | handler_kind, routing_target, routing_reason, handoff_* |
| `ponti_turn_summary` | Al completar turno | routed_agent, tool_calls_count, tokens_*, evidence_injected |
| `insight_evidence_injected` | Al inyectar evidencia previa | scope, period |
| `insights.compute` | Al computar insights | computed, created, rules_created |
| `insights.summary` | Al consultar summary | new_total, new_high |

---

## 8. Escalamiento

Si el incidente no se resuelve:
1. Verificar que el problema es reproducible con un curl directo al servicio
2. Capturar logs completos: `docker logs pymes-ponti-ai-1 > /tmp/ponti-ai-logs.txt 2>&1`
3. Verificar estado de la DB: conexiones activas, locks, tamaño de tablas
4. Si es performance: revisar tokens_input/tokens_output en `ponti_turn_summary` — prompts muy largos pueden causar latencia
