from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ingest_orquestator_server.api.dependencies import get_file_ingestion_service
from ingest_orquestator_server.application.exceptions import UnsupportedParserError
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.models.ingest_response import IngestResponse

router = APIRouter(prefix="/v1/ingest")


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    parser: Annotated[str, Query()] = "docling",
    include_document: Annotated[bool, Query()] = True,
) -> IngestResponse:
    try:
        return await service.ingest_upload(
            upload=file,
            parser_name=parser,
            include_document=include_document,
        )
    except UnsupportedParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {exc}") from exc
