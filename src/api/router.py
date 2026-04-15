"""Rutas HTTP del asistente de chat Ponti."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from runtime.logging import get_logger, get_request_id

from src.agents.service import iter_ponti_chat_sse, run_ponti_chat_turn
from src.api.chat_contract import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    ConversationMessage,
    ConversationSummary,
)
from src.api.deps import AppContainer, AuthContext, get_container, require_headers
from src.db.repository import AIRepository

router = APIRouter(prefix="/v1/chat", tags=["chat"])
logger = get_logger(__name__)


def _get_repo(container: AppContainer) -> AIRepository:
    return AIRepository(container.settings)


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ConversationListResponse:
    repo = _get_repo(container)
    rows = repo.list_conversations(project_id=auth.tenant_id, user_id=auth.actor, limit=limit)
    return ConversationListResponse(
        items=[
            ConversationSummary(
                id=r.id,
                title=r.title,
                created_at=r.created_at.isoformat() if r.created_at else "",
                updated_at=r.updated_at.isoformat() if r.updated_at else "",
                message_count=len(r.messages),
            )
            for r in rows
        ]
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ConversationDetail:
    repo = _get_repo(container)
    row = repo.get_conversation(auth.tenant_id, conversation_id)
    if row is None or row.user_id != auth.actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation_not_found")
    return ConversationDetail(
        id=row.id,
        title=row.title,
        messages=[
            ConversationMessage(
                role=str(m.get("role", "")),
                content=str(m.get("content", "")),
                ts=str(m.get("ts") or ""),
                tool_calls=list(m.get("tool_calls") or []),
                routed_agent=m.get("routed_agent"),
                routing_source=m.get("routing_source"),
            )
            for m in row.messages
        ],
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.post("", response_model=ChatResponse)
async def ponti_assistant_chat(
    req: ChatRequest,
    request: Request,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ChatResponse:
    request_id = get_request_id() or str(uuid4())
    repo = _get_repo(container)

    logger.info(
        "ponti_chat_started",
        request_id=request_id,
        project_id=auth.tenant_id,
        user_id=auth.actor,
        chat_id=req.chat_id or "",
        route_hint=req.route_hint or "",
    )

    try:
        result = await run_ponti_chat_turn(
            request_id=request_id,
            project_id=auth.tenant_id,
            user_id=auth.actor,
            message=req.message,
            chat_id=req.chat_id,
            route_hint=req.route_hint,
            chat_context=req.handoff.model_dump(mode="json") if req.handoff else None,
            preferred_language=req.preferred_language,
            accept_language=request.headers.get("Accept-Language"),
            settings=container.settings,
            llm=container.chat_llm,
            get_summary=container.get_summary,
            repo=repo,
            workspace=req.workspace.model_dump(mode="json") if req.workspace else None,
        )
    except ValueError as exc:
        if "conversation_not_found" in str(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation_not_found") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ChatResponse(**result)


@router.post("/stream")
async def ponti_assistant_chat_stream(
    req: ChatRequest,
    request: Request,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
):
    request_id = get_request_id() or str(uuid4())
    repo = _get_repo(container)

    logger.info(
        "ponti_chat_stream_started",
        request_id=request_id,
        project_id=auth.tenant_id,
        user_id=auth.actor,
        chat_id=req.chat_id or "",
        route_hint=req.route_hint or "",
    )

    async def event_generator():
        async for event in iter_ponti_chat_sse(
            request_id=request_id,
            project_id=auth.tenant_id,
            user_id=auth.actor,
            message=req.message,
            chat_id=req.chat_id,
            route_hint=req.route_hint,
            chat_context=req.handoff.model_dump(mode="json") if req.handoff else None,
            preferred_language=req.preferred_language,
            accept_language=request.headers.get("Accept-Language"),
            settings=container.settings,
            llm=container.chat_llm,
            get_summary=container.get_summary,
            repo=repo,
            workspace=req.workspace.model_dump(mode="json") if req.workspace else None,
        ):
            yield f"event: {event.get('event', 'message')}\ndata: {event.get('data', '{}')}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Request-ID": request_id},
    )
