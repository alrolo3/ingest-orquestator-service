import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ingest_orquestator_server.api.dependencies import shutdown_background_services
from ingest_orquestator_server.api.routes.capabilities import router as capabilities_router
from ingest_orquestator_server.api.routes.health import router as health_router
from ingest_orquestator_server.api.routes.ingestion import router as ingestion_router
from ingest_orquestator_server.config.settings import get_settings
from ingest_orquestator_server.infrastructure.docling.remote_llm_health import (
    RemoteLlmHealthChecker,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="Ingest Orquestator Server",
        version="0.1.0",
        description="Docling-based ingestion orchestration service.",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(capabilities_router)
    app.include_router(ingestion_router)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    _validate_remote_llm_on_startup()
    yield
    shutdown_background_services()


def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(message)s",
    )


def _validate_remote_llm_on_startup() -> None:
    settings = get_settings()
    if not settings.docling_remote_llm_health_check_enabled:
        return

    result = RemoteLlmHealthChecker(settings).check()
    if result.ok:
        logger.info(
            "remote_llm.health.ok url=%s model=%s status_code=%s",
            result.url,
            result.model,
            result.status_code,
        )
        return

    logger.error(
        "remote_llm.health.failed url=%s model=%s status_code=%s error=%s",
        result.url,
        result.model,
        result.status_code,
        result.error,
    )
    raise RuntimeError(f"RemoteLLM health check failed: {result.error}")
