from fastapi import APIRouter

from ingest_orquestator_server.api.dependencies import SettingsDependency
from ingest_orquestator_server.infrastructure.docling.remote_llm_health import (
    RemoteLlmHealthChecker,
)

router = APIRouter()


@router.get("/health")
def health(settings: SettingsDependency) -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok"}


@router.get("/health/remote-llm")
def remote_llm_health(settings: SettingsDependency) -> dict[str, object]:
    return RemoteLlmHealthChecker(settings).check().to_dict()
