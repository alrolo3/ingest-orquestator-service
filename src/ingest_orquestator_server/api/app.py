from fastapi import FastAPI

from ingest_orquestator_server.api.routes.health import router as health_router
from ingest_orquestator_server.api.routes.ingestion import router as ingestion_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ingest Orquestator Server",
        version="0.1.0",
        description="Docling-based ingestion orchestration service.",
    )
    app.include_router(health_router)
    app.include_router(ingestion_router)
    return app
