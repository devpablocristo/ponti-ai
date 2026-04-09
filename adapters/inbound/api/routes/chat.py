"""Rutas /v1/chat y conversaciones persistidas."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from runtime.api.events import to_sse_event
from runtime.logging import get_logger, get_request_id

from adapters.inbound.api.auth.headers import require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    ConversationMessage,
    ConversationSummary,
)
from adapters.outbound.db.repos.conversation_repo_pg import ConversationRepositoryPG
from adapters.outbound.db.repos.project_dossier_repo_pg import ProjectDossierRepositoryPG
from contexts.chat.application.run_ponti_chat import iter_ponti_chat_sse, run_ponti_chat_turn
from runtime.contexts import AuthContext
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/v1/chat", tags=["chat"])
logger = get_logger(__name__)


def _repo(container: AppContainer) -> ConversationRepositoryPG:
    return ConversationRepositoryPG(container.settings)


def _dossier_repo(container: AppContainer) -> ProjectDossierRepositoryPG:
    return ProjectDossierRepositoryPG(container.settings)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    container: AppContainer = Depends(get_container),
    auth: AuthContext = Depends(require_headers),
    limit: int = Query(default=50, ge=1, le=200),
):
    if not container.settings.chat_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat disabled")
    repo = _repo(container)
    rows = await asyncio.to_thread(
        repo.list_conversations,
        project_id=auth.tenant_id,
        user_id=auth.actor,
        limit=limit,
    )
    return ConversationListResponse(
        items=[
            ConversationSummary(
                id=r.id,
                title=r.title or "Sin título",
                created_at=r.created_at.isoformat() if r.created_at else "",
                updated_at=r.updated_at.isoformat() if r.updated_at else "",
                message_count=len(r.messages) if r.messages else 0,
            )
            for r in rows
        ]
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str = Path(..., min_length=32, max_length=40),
    container: AppContainer = Depends(get_container),
    auth: AuthContext = Depends(require_headers),
):
    if not container.settings.chat_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat disabled")
    repo = _repo(container)
    row = await asyncio.to_thread(repo.get_conversation, auth.tenant_id, conversation_id)
    if row is None or row.user_id != auth.actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    return ConversationDetail(
        id=row.id,
        title=row.title or "Sin título",
        messages=[
            ConversationMessage(
                role=str(m.get("role", "")),
                content=str(m.get("content", "")),
                ts=m.get("ts"),
                tool_calls=list(m.get("tool_calls") or []),
            )
            for m in (row.messages or [])
        ],
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.post("", response_model=ChatResponse)
async def ponti_assistant_chat(
    req: ChatRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
    auth: AuthContext = Depends(require_headers),
):
    if not container.settings.chat_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat disabled")

    request_id = get_request_id() or str(uuid4())
    logger.info(
        "ponti_chat_started",
        request_id=request_id,
        project_id=auth.tenant_id,
        user_id=auth.actor,
        chat_id=req.chat_id or "",
        route_hint=req.route_hint or "",
    )

    repo = _repo(container)
    dossier_repo = _dossier_repo(container)
    try:
        payload = await run_ponti_chat_turn(
            request_id=request_id,
            project_id=auth.tenant_id,
            user_id=auth.actor,
            message=req.message,
            chat_id=req.chat_id,
            route_hint=req.route_hint,
            preferred_language=req.preferred_language,
            accept_language=request.headers.get("Accept-Language"),
            settings=container.settings,
            llm=container.chat_llm,
            get_summary=container.get_summary,
            repo=repo,
            dossier_repo=dossier_repo,
        )
    except ValueError as exc:
        if str(exc) == "conversation_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("ponti_chat_failed", project_id=auth.tenant_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ai unavailable") from exc

    logger.info(
        "ponti_chat_completed",
        request_id=request_id,
        project_id=auth.tenant_id,
        chat_id=payload.get("chat_id"),
        routed_agent=payload.get("routed_agent"),
    )
    return ChatResponse.model_validate(payload)


@router.post("/stream")
async def ponti_assistant_chat_stream(
    req: ChatRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
    auth: AuthContext = Depends(require_headers),
):
    """Mismo cuerpo que POST /v1/chat; respuesta SSE (eventos start, text, tool_*, done)."""
    if not container.settings.chat_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat disabled")

    request_id = get_request_id() or str(uuid4())
    repo = _repo(container)
    dossier_repo = _dossier_repo(container)

    async def event_gen():
        try:
            async for item in iter_ponti_chat_sse(
                request_id=request_id,
                project_id=auth.tenant_id,
                user_id=auth.actor,
                message=req.message,
                chat_id=req.chat_id,
                route_hint=req.route_hint,
                preferred_language=req.preferred_language,
                accept_language=request.headers.get("Accept-Language"),
                settings=container.settings,
                llm=container.chat_llm,
                get_summary=container.get_summary,
                repo=repo,
                dossier_repo=dossier_repo,
            ):
                yield item
        except Exception as exc:  # noqa: BLE001
            logger.exception("ponti_chat_stream_failed", project_id=auth.tenant_id, error=str(exc))
            yield to_sse_event("error", {"message": "stream_failed", "detail": str(exc)})

    return EventSourceResponse(event_gen())
