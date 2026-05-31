from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ingest_orquestator_server.api.dependencies import (
    get_file_ingestion_service,
    get_job_query_service,
    get_output_retrieval_service,
)
from ingest_orquestator_server.application.exceptions import (
    JobNotFoundError,
    OutputArtifactNotFoundError,
    UnsupportedDocumentFormatError,
    UnsupportedIngestionOptionError,
    UnsupportedParserError,
    UnsupportedPipelineError,
    UploadValidationError,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
    OutputType,
)
from ingest_orquestator_server.models.ingest_batch_response import IngestBatchResponse
from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.output_files import OutputFiles

router = APIRouter(prefix="/v1/ingest")


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    parser: Annotated[str, Query()] = "docling",
    pipeline: Annotated[str | None, Query()] = None,
    chunking_enabled: Annotated[bool | None, Query()] = None,
    chunking_strategy: Annotated[str | None, Query()] = None,
    async_mode: Annotated[bool, Query()] = False,
    include_document: Annotated[bool, Query()] = True,
) -> IngestResponse:
    try:
        return await service.ingest_upload(
            upload=file,
            parser_name=parser,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
            include_document=include_document,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (
        UnsupportedParserError,
        UnsupportedDocumentFormatError,
        UnsupportedIngestionOptionError,
        UnsupportedPipelineError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {exc}") from exc


@router.post("/files", response_model=IngestBatchResponse)
async def ingest_files(
    files: Annotated[list[UploadFile], File()],
    service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    parser: Annotated[str, Query()] = "docling",
    pipeline: Annotated[str | None, Query()] = None,
    chunking_enabled: Annotated[bool | None, Query()] = None,
    chunking_strategy: Annotated[str | None, Query()] = None,
) -> IngestBatchResponse:
    try:
        return await service.enqueue_uploads(
            uploads=list(files),
            parser_name=parser,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (
        UnsupportedParserError,
        UnsupportedDocumentFormatError,
        UnsupportedIngestionOptionError,
        UnsupportedPipelineError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue files: {exc}") from exc


@router.get("/jobs", response_model=list[IngestionJob])
def list_jobs(
    service: Annotated[JobQueryService, Depends(get_job_query_service)],
    ids: Annotated[str | None, Query(description="Comma-separated job ids.")] = None,
) -> list[IngestionJob]:
    job_ids = [job_id.strip() for job_id in (ids or "").split(",") if job_id.strip()]
    if len(job_ids) > 100:
        raise HTTPException(status_code=400, detail="At most 100 job ids can be requested.")
    return service.list_jobs(job_ids)


@router.get("/jobs/{job_id}", response_model=IngestionJob)
def get_job(
    job_id: str,
    service: Annotated[JobQueryService, Depends(get_job_query_service)],
) -> IngestionJob:
    try:
        return service.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/outputs", response_model=OutputFiles)
def list_outputs(
    job_id: str,
    service: Annotated[OutputRetrievalService, Depends(get_output_retrieval_service)],
) -> OutputFiles:
    try:
        return service.list_outputs(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OutputArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/outputs/{output_type}")
def get_output(
    job_id: str,
    output_type: OutputType,
    service: Annotated[OutputRetrievalService, Depends(get_output_retrieval_service)],
) -> FileResponse:
    try:
        output_path = service.get_output_path(job_id, output_type)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OutputArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        output_path,
        media_type=service.content_type_for(output_type),
        filename=output_path.name,
    )
