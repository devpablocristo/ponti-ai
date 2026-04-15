"""Punto de entrada de la aplicación Ponti AI.

Hoy ponti-ai es solo el copilot conversacional (`POST /v1/chat`,
`POST /v1/chat/stream`, conversaciones). Los insights "vivos" se generaron
y persisten en ponti-backend (`business_insight_candidates`); ponti-ai
solo lee el resumen local (legacy, casi siempre vacío) para nutrir el
dossier del agente.
"""

from fastapi import FastAPI

from src.agents.chat_provider_factory import build_chat_llm_provider
from src.api.deps import AppContainer
from src.api.health import router as health_router
from src.api.router import router as chat_router
from src.config import load_settings
from src.insights.repository import InsightRepositoryPG
from src.insights.service import GetSummary


def create_app() -> FastAPI:
    settings = load_settings()

    insight_repo = InsightRepositoryPG(settings)
    chat_llm = build_chat_llm_provider(settings)
    get_summary = GetSummary(insight_repo)

    container = AppContainer(
        settings=settings,
        get_summary=get_summary,
        chat_llm=chat_llm,
    )

    app = FastAPI(title="Ponti AI", version="2.1.0")
    app.state.settings = settings
    app.state.container = container

    app.include_router(health_router)
    if settings.chat_enabled:
        app.include_router(chat_router)

    return app
