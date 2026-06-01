from __future__ import annotations

from pathlib import Path

from ingest_orquestator_server.infrastructure.filesystem.json_file_writer import JsonFileWriter
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent


class LocalParseOutputWriter:
    def __init__(self, json_writer: JsonFileWriter | None = None) -> None:
        self._json_writer = json_writer or JsonFileWriter()

    def write(
        self,
        content: ParsedDocumentContent,
        output_root: Path,
        *,
        diagnostics: ParseDiagnostics | None = None,
    ) -> OutputFiles:
        output_dir = output_root / content.document_id
        output_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = output_dir / "document.md"
        metadata_json = output_dir / "document_metadata.json"
        rag_chunks_jsonl = output_dir / "rag_chunks.jsonl"
        html_path = output_dir / "document.html" if content.html is not None else None

        markdown_path.write_text(content.markdown, encoding="utf-8")
        rag_chunks_jsonl.write_text(
            "\n".join(record.model_dump_json() for record in content.rag_records)
            + ("\n" if content.rag_records else ""),
            encoding="utf-8",
        )
        if html_path is not None:
            html_path.write_text(content.html or "", encoding="utf-8")
        self._json_writer.write(
            metadata_json,
            {
                **content.metadata,
                "document_id": content.document_id,
                "rag_record_count": len(content.rag_records),
                "diagnostics": diagnostics.model_dump(mode="json") if diagnostics else None,
            },
        )

        return OutputFiles(
            output_dir=output_dir,
            markdown=markdown_path,
            document_metadata_json=metadata_json,
            rag_chunks_jsonl=rag_chunks_jsonl,
            html=html_path,
            manifest_json=metadata_json,
        )
