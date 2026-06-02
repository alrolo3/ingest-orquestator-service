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
        chunking_metadata: dict[str, object] | None = None,
    ) -> list[RagIngestionRecord]:
        chunking_metadata = chunking_metadata or {}
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
                    chunking_metadata=chunking_metadata,
                )
                for index, chunk in enumerate(chunks)
                if chunk.text.strip()
            ]
        content = document.markdown.strip() or document.text.strip()
        if not content:
            return []
        metadata = self._metadata(
            document=document,
            confidence_summary=confidence_summary,
            warnings=warnings,
            chunking_metadata=chunking_metadata,
        )
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
                **self._contract_fields(
                    content=content,
                    document=document,
                    metadata=metadata,
                    confidence_summary=confidence_summary,
                ),
                metadata=metadata,
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
        chunking_metadata: dict[str, object],
    ) -> RagIngestionRecord:
        content = chunk.text.strip()
        metadata = self._metadata(
            document=document,
            chunk=chunk,
            confidence_summary=confidence_summary,
            warnings=warnings,
            chunking_metadata=chunking_metadata,
        )
        return RagIngestionRecord(
            record_id=f"{document.document_id}:rag:{index + 1}",
            document_id=document.document_id,
            job_id=job_id,
            content=content,
            title=document.title,
            source_file_name=document.source_file_name,
            input_format=input_format,
            parser=parser,
            pipeline=pipeline,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            chunk_id=chunk.chunk_id,
            record_type=RagRecordType.CHUNK,
            **self._contract_fields(
                content=content,
                document=document,
                metadata=metadata,
                confidence_summary=confidence_summary,
            ),
            metadata=metadata,
        )

    def _contract_fields(
        self,
        *,
        content: str,
        document: ParsedDocument,
        metadata: dict[str, Any],
        confidence_summary: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "clean_title": self._clean_title(document=document, metadata=metadata),
            "page_count": self._page_count(document=document, metadata=metadata),
            "headings": self._string_list(metadata.get("headings")),
            "element_types": self._string_list(metadata.get("element_types")),
            "chunking_strategy": self._string_value(metadata.get("chunking_strategy")),
            "searchable": self._bool_value(metadata.get("searchable"), default=True),
            "boilerplate": self._bool_value(metadata.get("boilerplate"), default=False),
            "content_kind": self._string_value(metadata.get("content_kind")) or "unknown",
            "content_length": len(content),
            "token_count": self._int_value(metadata.get("token_count")),
            "chunk_quality": self._float_value(metadata.get("chunk_quality")),
            "confidence": confidence_summary or None,
        }

    def _metadata(
        self,
        *,
        document: ParsedDocument,
        confidence_summary: dict[str, Any],
        warnings: list[dict[str, Any]],
        chunk: DocumentChunk | None = None,
        chunking_metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "mime_type": document.mime_type,
            "page_count": document.page_count,
            "confidence_summary": confidence_summary,
            "warning_count": len(warnings),
            "warnings": warnings,
            **(chunking_metadata or {}),
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

    def _clean_title(self, *, document: ParsedDocument, metadata: dict[str, Any]) -> str | None:
        headings = self._string_list(metadata.get("headings"))
        if headings:
            return headings[0]
        return self._string_value(document.title) or self._string_value(document.source_file_name)

    def _page_count(self, *, document: ParsedDocument, metadata: dict[str, Any]) -> int | None:
        return self._int_value(metadata.get("page_count")) or self._int_value(document.page_count)

    def _string_value(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    def _string_list(self, value: Any) -> list[str] | None:
        if isinstance(value, str):
            string_value = self._string_value(value)
            return [string_value] if string_value is not None else None
        if not isinstance(value, list):
            return None
        values = [self._string_value(item) for item in value]
        cleaned = [item for item in values if item is not None]
        return cleaned or None

    def _bool_value(self, value: Any, *, default: bool | None = None) -> bool | None:
        if isinstance(value, bool):
            return value
        return default

    def _int_value(self, value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    def _float_value(self, value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return float(value)
