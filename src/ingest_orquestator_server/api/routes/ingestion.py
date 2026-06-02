from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ingest_orquestator_server.api.dependencies import (
    get_document_run_query_service,
    get_file_ingestion_service,
    get_job_query_service,
    get_job_removal_service,
    get_output_retrieval_service,
    get_queue_metrics_service,
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
from ingest_orquestator_server.application.services.document_run_query_service import (
    DocumentRunQueryService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.job_removal_service import (
    JobRemovalService,
)
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
    OutputType,
)
from ingest_orquestator_server.application.services.queue_metrics_service import (
    QueueMetricsService,
)
from ingest_orquestator_server.models.ingest_batch_response import IngestBatchResponse
from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_document import (
    IngestDocumentsResponse,
    IngestionDocumentEnvelope,
    IngestionDocumentListResponse,
    IngestionRunListResponse,
    IngestionRunSummary,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.job_removal import JobRemovalResult
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.queue_metrics import QueueMetrics

router = APIRouter(prefix="/v1/ingest")


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    parser: Annotated[str, Query()] = "docling",
    pipeline: Annotated[str | None, Query()] = None,
    chunking_enabled: Annotated[bool | None, Query()] = None,
    chunking_strategy: Annotated[str | None, Query()] = None,
    dispatch_sink_mode: Annotated[str | None, Query()] = None,
    ocr_languages: Annotated[str | None, Query()] = None,
    include_html: Annotated[bool, Query()] = False,
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
            dispatch_sink_mode=dispatch_sink_mode,
            ocr_languages=ocr_languages,
            include_html=include_html,
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
    dispatch_sink_mode: Annotated[str | None, Query()] = None,
    ocr_languages: Annotated[str | None, Query()] = None,
    include_html: Annotated[bool, Query()] = False,
) -> IngestBatchResponse:
    try:
        return await service.enqueue_uploads(
            uploads=list(files),
            parser_name=parser,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
            dispatch_sink_mode=dispatch_sink_mode,
            ocr_languages=ocr_languages,
            include_html=include_html,
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


@router.post("/documents", response_model=IngestDocumentsResponse)
async def ingest_documents(
    files: Annotated[list[UploadFile], File()],
    ingestion_service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    document_service: Annotated[
        DocumentRunQueryService,
        Depends(get_document_run_query_service),
    ],
    parser: Annotated[str, Query()] = "docling",
    pipeline: Annotated[str | None, Query()] = None,
    chunking_enabled: Annotated[bool | None, Query()] = None,
    chunking_strategy: Annotated[str | None, Query()] = None,
    dispatch_sink_mode: Annotated[str | None, Query()] = None,
    ocr_languages: Annotated[str | None, Query()] = None,
    include_html: Annotated[bool, Query()] = False,
) -> IngestDocumentsResponse:
    try:
        response = await ingestion_service.enqueue_uploads(
            uploads=list(files),
            parser_name=parser,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
            dispatch_sink_mode=dispatch_sink_mode,
            ocr_languages=ocr_languages,
            include_html=include_html,
        )
        document_ids = [
            job.document_id for job in response.jobs if job.document_id is not None
        ]
        return IngestDocumentsResponse(
            documents=[
                document_service.get_document(document_id)
                for document_id in dict.fromkeys(document_ids)
            ],
            failed=response.failed,
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


@router.get("/documents", response_model=IngestionDocumentListResponse)
def list_documents(
    service: Annotated[DocumentRunQueryService, Depends(get_document_run_query_service)],
    status: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> IngestionDocumentListResponse:
    return service.list_documents(status=status, q=q, limit=limit, cursor=cursor)


@router.get("/documents/{document_id}", response_model=IngestionDocumentEnvelope)
def get_document(
    document_id: str,
    service: Annotated[DocumentRunQueryService, Depends(get_document_run_query_service)],
) -> IngestionDocumentEnvelope:
    try:
        return service.get_document(document_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/{document_id}/runs", response_model=IngestionRunSummary)
def create_document_run(
    document_id: str,
    ingestion_service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
    document_service: Annotated[
        DocumentRunQueryService,
        Depends(get_document_run_query_service),
    ],
    parser: Annotated[str, Query()] = "docling",
    pipeline: Annotated[str | None, Query()] = None,
    chunking_enabled: Annotated[bool | None, Query()] = None,
    chunking_strategy: Annotated[str | None, Query()] = None,
    dispatch_sink_mode: Annotated[str | None, Query()] = None,
    ocr_languages: Annotated[str | None, Query()] = None,
    include_html: Annotated[bool, Query()] = False,
) -> IngestionRunSummary:
    try:
        response = ingestion_service.enqueue_document_run(
            document_id=document_id,
            parser_name=parser,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
            dispatch_sink_mode=dispatch_sink_mode,
            ocr_languages=ocr_languages,
            include_html=include_html,
        )
        return document_service.get_run(response.job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        UnsupportedParserError,
        UnsupportedDocumentFormatError,
        UnsupportedIngestionOptionError,
        UnsupportedPipelineError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=IngestionRunListResponse)
def list_runs(
    service: Annotated[DocumentRunQueryService, Depends(get_document_run_query_service)],
    ids: Annotated[str | None, Query(description="Comma-separated run ids.")] = None,
) -> IngestionRunListResponse:
    run_ids = [run_id.strip() for run_id in (ids or "").split(",") if run_id.strip()]
    if len(run_ids) > 100:
        raise HTTPException(status_code=400, detail="At most 100 run ids can be requested.")
    return IngestionRunListResponse(runs=service.list_runs(run_ids))


@router.get("/runs/{run_id}", response_model=IngestionRunSummary)
def get_run(
    run_id: str,
    service: Annotated[DocumentRunQueryService, Depends(get_document_run_query_service)],
) -> IngestionRunSummary:
    try:
        return service.get_run(run_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/outputs", response_model=OutputFiles)
def list_run_outputs(
    run_id: str,
    service: Annotated[OutputRetrievalService, Depends(get_output_retrieval_service)],
) -> OutputFiles:
    return list_outputs(run_id, service)


@router.get("/jobs", response_model=list[IngestionJob])
def list_jobs(
    service: Annotated[JobQueryService, Depends(get_job_query_service)],
    ids: Annotated[str | None, Query(description="Comma-separated job ids.")] = None,
) -> list[IngestionJob]:
    job_ids = [job_id.strip() for job_id in (ids or "").split(",") if job_id.strip()]
    if len(job_ids) > 100:
        raise HTTPException(status_code=400, detail="At most 100 job ids can be requested.")
    return service.list_jobs(job_ids)


@router.get("/queue/metrics", response_model=QueueMetrics)
def queue_metrics(
    service: Annotated[QueueMetricsService, Depends(get_queue_metrics_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> QueueMetrics:
    return service.metrics(recent_limit=limit)


@router.get("/jobs/{job_id}", response_model=IngestionJob)
def get_job(
    job_id: str,
    service: Annotated[JobQueryService, Depends(get_job_query_service)],
) -> IngestionJob:
    try:
        return service.get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}", response_model=JobRemovalResult)
def delete_job(
    job_id: str,
    service: Annotated[JobRemovalService, Depends(get_job_removal_service)],
) -> JobRemovalResult:
    result = service.remove_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return result


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
