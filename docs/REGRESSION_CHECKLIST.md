# Checklist de regresión — Ponti AI

Verificación manual antes de cada release o merge significativo.

## Chat

- [ ] Chat libre sin hint: enviar mensaje genérico, recibir respuesta coherente
- [ ] Chat con hint de dominio (labors, supplies, campaigns, lots, stock, reports): verifica que `routed_agent` coincida
- [ ] Chat con hint `dashboard`: pregunta ejecutiva, verifica routing a dashboard
- [ ] Chat con hint `insight_chat`: verifica routing a insight_chat
- [ ] Streaming SSE: enviar mensaje por `/v1/chat/stream`, verificar eventos `start`, `text`, `done`
- [ ] Conversación existente: enviar `chat_id` válido, verificar que se agrega al historial
- [ ] Conversación inexistente: enviar `chat_id` inválido, verificar error
- [ ] Mensaje vacío: verificar respuesta estática sin LLM

## Routing pipeline

- [ ] Menú: enviar "menú" o "opciones", verificar respuesta estática con acciones
- [ ] Clarificación: enviar "resumen" sin hint, verificar clarificación
- [ ] Handoff insight: enviar con `handoff.insight_id`, verificar routing a insight_lane
- [ ] Handoff inválido: enviar handoff sin insight_id, verificar fallback a orchestrator
- [ ] Follow-up contextual: en conversación con insight previo, enviar "explicame más", verificar carry-forward

## Insight evidence (Fase 6)

- [ ] Primer turno con handoff: verificar que `insight_evidence` aparece en assistant_msg
- [ ] Follow-up: verificar que se inyecta system message con evidencia previa
- [ ] TTL 24h: evidencia más vieja de 24h no se inyecta

## Notificaciones (Fase 7-8)

- [ ] Frontend: "Explicar en chat" en notificaciones navega a AIAssistant con handoff
- [ ] AIAssistant consume handoff de sessionStorage al montar
- [ ] Trigger Go: mutación → compute → summary → SyncFromSummary con chat_context
- [ ] Idempotencia: ejecutar sync dos veces, verificar que no duplica notificaciones

## Insights + Copilot

- [ ] `POST /v1/insights/compute`: retorna insights computados
- [ ] `GET /v1/insights/summary`: retorna resumen con top insights
- [ ] `GET /v1/copilot/insights/{id}/explain`: retorna explicación
- [ ] `POST /v1/insights/{id}/actions`: registra acción (ack, snooze, resolve)

## Observabilidad (Fase 9)

- [ ] Log `ponti_turn_routing_decision`: verificar campos handler_kind, routing_target, routing_reason, handoff_*
- [ ] Log `ponti_turn_summary`: verificar campos routed_agent, tool_calls_count, tokens_*, evidence_injected
- [ ] Log `insight_evidence_injected`: verificar scope y period
- [ ] Audit event: verificar que `record_agent_event` persiste metadata

## Health

- [ ] `GET /healthz`: responde 200
- [ ] `GET /readyz`: responde 200
- [ ] `GET /v1/version`: retorna versión del servicio
