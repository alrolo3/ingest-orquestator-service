from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from ingest_orquestator_server.config import get_settings
from ingest_orquestator_server.models import IngestionStatus, IngestResponse
from ingest_orquestator_server.output_writer import write_parse_output
from ingest_orquestator_server.parsers.docling_parser import DoclingParser
from ingest_orquestator_server.storage import save_upload_file

settings = get_settings()

app = FastAPI(
    title="Ingest Orquestator Server",
    version="0.1.0",
    description="Docling-based ingestion orchestration service.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok"}


@app.post("/v1/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    parser: Annotated[str, Query()] = "docling",
    include_document: Annotated[bool, Query()] = True,
) -> IngestResponse:
    if parser != "docling":
        raise HTTPException(status_code=400, detail=f"Unsupported parser: {parser}")

    job_id = str(uuid4())
    upload_path = await save_upload_file(file, settings.uploads_dir, job_id=job_id)

    try:
        parse_output = DoclingParser().parse(upload_path, document_id=job_id)
        outputs = write_parse_output(parse_output, settings.outputs_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {exc}") from exc

    return IngestResponse(
        job_id=job_id,
        status=IngestionStatus.COMPLETED,
        parser=parser,
        document_id=parse_output.document.document_id,
        input_path=upload_path,
        outputs=outputs,
        document=parse_output.document if include_document else None,
    )
