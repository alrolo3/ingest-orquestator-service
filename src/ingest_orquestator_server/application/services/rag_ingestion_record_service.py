from __future__ import annotations

from typing import Any

from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.parsed_document import ParsedDocument
from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord, RagRecordType


class RagIngestionRecordService:
    def build_records(
        self,
        *,
        document: ParsedDocument,
        chunks: list[DocumentChunk],
        job_id: str,
        parser: str,
        pipeline: str | None,
        input_format: str | None,
        confidence_summary: dict[str, Any],
        warnings: list[dict[str, Any]],
    ) -> list[RagIngestionRecord]:
        if chunks:
            return [
                self._chunk_record(
                    document=document,
                    chunk=chunk,
                    index=index,
                    job_id=job_id,
                    parser=parser,
                    pipeline=pipeline,
                    input_format=input_format,
                    confidence_summary=confidence_summary,
                    warnings=warnings,
                )
                for index, chunk in enumerate(chunks)
                if chunk.text.strip()
            ]
        content = document.markdown.strip() or document.text.strip()
        if not content:
            return []
        return [
            RagIngestionRecord(
                record_id=f"{document.document_id}:document",
                document_id=document.document_id,
                job_id=job_id,
                content=content,
                title=document.title,
                source_file_name=document.source_file_name,
                input_format=input_format,
                parser=parser,
                pipeline=pipeline,
                record_type=RagRecordType.DOCUMENT,
                metadata=self._metadata(
                    document=document,
                    confidence_summary=confidence_summary,
                    warnings=warnings,
                ),
            )
        ]

    def _chunk_record(
        self,
        *,
        document: ParsedDocument,
        chunk: DocumentChunk,
        index: int,
        job_id: str,
        parser: str,
        pipeline: str | None,
        input_format: str | None,
        confidence_summary: dict[str, Any],
        warnings: list[dict[str, Any]],
    ) -> RagIngestionRecord:
        return RagIngestionRecord(
            record_id=f"{document.document_id}:rag:{index + 1}",
            document_id=document.document_id,
            job_id=job_id,
            content=chunk.text.strip(),
            title=document.title,
            source_file_name=document.source_file_name,
            input_format=input_format,
            parser=parser,
            pipeline=pipeline,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            chunk_id=chunk.chunk_id,
            record_type=RagRecordType.CHUNK,
            metadata=self._metadata(
                document=document,
                chunk=chunk,
                confidence_summary=confidence_summary,
                warnings=warnings,
            ),
        )

    def _metadata(
        self,
        *,
        document: ParsedDocument,
        confidence_summary: dict[str, Any],
        warnings: list[dict[str, Any]],
        chunk: DocumentChunk | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "mime_type": document.mime_type,
            "page_count": document.page_count,
            "confidence_summary": confidence_summary,
            "warning_count": len(warnings),
            "warnings": warnings,
        }
        if chunk is not None:
            metadata |= {
                key: value
                for key, value in chunk.metadata.items()
                if key not in {"source_path", "raw_text"}
            }
        return {
            key: value
            for key, value in metadata.items()
            if value not in (None, "", [], {})
        }
