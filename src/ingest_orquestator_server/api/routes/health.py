from typing import Annotated

from fastapi import APIRouter, Depends

from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.remote_llm_health import (
    RemoteLlmHealthChecker,
)

router = APIRouter()


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok"}


@router.get("/health/remote-llm")
def remote_llm_health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    return RemoteLlmHealthChecker(settings).check().to_dict()
