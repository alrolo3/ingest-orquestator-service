from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from ingest_orquestator_server.application.exceptions import (
    JobNotFoundError,
    OutputArtifactNotFoundError,
)
from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.models.output_files import OutputFiles


class OutputType(StrEnum):
    MANIFEST = "manifest"
    NORMALIZED = "normalized"
    MARKDOWN = "markdown"
    TEXT = "text"
    RAW = "raw"
    HTML = "html"
    CHUNKS = "chunks"
    EMBEDDING = "embedding"
    CONFIDENCE = "confidence"


class OutputRetrievalService:
    _content_types = {
        OutputType.MANIFEST: "application/json",
        OutputType.NORMALIZED: "application/json",
        OutputType.MARKDOWN: "text/markdown; charset=utf-8",
        OutputType.TEXT: "text/plain; charset=utf-8",
        OutputType.RAW: "application/json",
        OutputType.HTML: "text/html; charset=utf-8",
        OutputType.CHUNKS: "application/json",
        OutputType.EMBEDDING: "application/x-ndjson",
        OutputType.CONFIDENCE: "application/json",
    }

    def __init__(self, job_repository: IngestionJobRepository) -> None:
        self._job_repository = job_repository

    def list_outputs(self, job_id: str) -> OutputFiles:
        job = self._job_repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        if job.outputs is None:
            raise OutputArtifactNotFoundError(job_id, "outputs")
        return job.outputs

    def get_output_path(self, job_id: str, output_type: OutputType) -> Path:
        outputs = self.list_outputs(job_id)
        output_path = self._path_for_type(outputs, output_type)
        if output_path is None or not output_path.is_file():
            raise OutputArtifactNotFoundError(job_id, output_type.value)
        return output_path

    def content_type_for(self, output_type: OutputType) -> str:
        return self._content_types[output_type]

    @staticmethod
    def _path_for_type(outputs: OutputFiles, output_type: OutputType) -> Path | None:
        if output_type == OutputType.MANIFEST:
            return outputs.manifest_json
        if output_type == OutputType.NORMALIZED:
            return outputs.normalized_json
        if output_type == OutputType.MARKDOWN:
            return outputs.markdown
        if output_type == OutputType.TEXT:
            return outputs.text
        if output_type == OutputType.RAW:
            return outputs.raw_docling_json
        if output_type == OutputType.HTML:
            return outputs.html
        if output_type == OutputType.CHUNKS:
            return outputs.chunks_json
        if output_type == OutputType.EMBEDDING:
            return outputs.embedding_input_jsonl
        if output_type == OutputType.CONFIDENCE:
            return outputs.confidence_json
        return None
