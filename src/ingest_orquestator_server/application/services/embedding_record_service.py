from __future__ import annotations

from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.embedding_record import EmbeddingRecord
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class EmbeddingRecordService:
    def build_records(
        self,
        *,
        document: ParsedDocument,
        chunks: list[DocumentChunk],
    ) -> list[EmbeddingRecord]:
        records: list[EmbeddingRecord] = []
        document_metadata = document.metadata.get("docling", {})
        for index, chunk in enumerate(chunks):
            text = chunk.text.strip()
            if not text:
                continue

            records.append(
                EmbeddingRecord(
                    record_id=f"{document.document_id}:embedding:{index + 1}",
                    document_id=document.document_id,
                    chunk_id=chunk.chunk_id,
                    text=text,
                    raw_text=chunk.metadata.get("raw_text"),
                    contextualized=bool(chunk.metadata.get("contextualized")),
                    metadata={
                        "source_file_name": document.source_file_name,
                        "source_path": document.source_path,
                        "title": document.title,
                        "mime_type": document.mime_type,
                        "input_format": document_metadata.get("input_format"),
                        "parser": document_metadata.get("parser", "docling"),
                        "pipeline": document_metadata.get("pipeline"),
                        "profile": document_metadata.get("profile"),
                        "runtime": document_metadata.get("runtime"),
                        "vlm_model": document_metadata.get("vlm_model"),
                        "vlm_runtime": document_metadata.get("vlm_runtime"),
                        "vlm_runtime_requested": document_metadata.get("vlm_runtime_requested"),
                        "picture_description_model": document_metadata.get(
                            "picture_description_model"
                        ),
                        "picture_description_runtime": document_metadata.get(
                            "picture_description_runtime"
                        ),
                        "picture_description_runtime_requested": document_metadata.get(
                            "picture_description_runtime_requested"
                        ),
                        "chunker_strategy": chunk.metadata.get("chunker_strategy"),
                        "confidence": document.metadata.get("docling_result", {}).get(
                            "confidence_summary", {}
                        ),
                        "warnings": document.metadata.get("docling_result", {}).get("warnings", []),
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        **chunk.metadata,
                    },
                )
            )
        return records
