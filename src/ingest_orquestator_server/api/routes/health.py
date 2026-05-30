from typing import Annotated

from fastapi import APIRouter, Depends

from ingest_orquestator_server.config.settings import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok"}
