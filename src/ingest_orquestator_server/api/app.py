import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ingest_orquestator_server.api.dependencies import shutdown_background_services
from ingest_orquestator_server.api.routes.health import router as health_router
from ingest_orquestator_server.api.routes.ingestion import router as ingestion_router


def create_app() -> FastAPI:
    _configure_logging()
    app = FastAPI(
        title="Ingest Orquestator Server",
        version="0.1.0",
        description="Docling-based ingestion orchestration service.",
        lifespan=_lifespan,
    )
    app.include_router(health_router)
    app.include_router(ingestion_router)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
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
