from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ingest_orquestator_server.api.dependencies import get_ingestor_settings_service
from ingest_orquestator_server.application.services.ingestor_settings_service import (
    IngestorSettingsService,
)
from ingest_orquestator_server.models.ingestor_settings import (
    IngestorSettingsResponse,
    IngestorSettingsUpdate,
)

router = APIRouter(prefix="/v1/ingest/settings")


@router.get("", response_model=IngestorSettingsResponse)
def ingestor_settings(
    service: Annotated[IngestorSettingsService, Depends(get_ingestor_settings_service)],
) -> IngestorSettingsResponse:
    return service.settings_response()


@router.patch("", response_model=IngestorSettingsResponse)
def update_ingestor_settings(
    update: IngestorSettingsUpdate,
    service: Annotated[IngestorSettingsService, Depends(get_ingestor_settings_service)],
) -> IngestorSettingsResponse:
    try:
        return service.update(update)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
