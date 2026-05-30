# Architecture

The MVP mirrors the ingestion side of a RAG pipeline without taking on retrieval infrastructure.

```text
FastAPI or CLI
-> file storage
-> parser interface
-> Docling parser
-> normalized document model
-> local output files
```

## Boundaries

- `parsers.base.DocumentParser` defines the parser contract.
- `parsers.docling_parser.DoclingParser` converts a source file into raw Docling output plus normalized output.
- `normalization.normalize_docling_document` maps Docling's document dictionary into project-owned models.
- `output_writer.write_parse_output` persists all debug-friendly artifacts.
- `main.py` exposes the HTTP API.
- `cli.py` exposes local parser runs.

## Current MVP Behavior

The service runs parsing synchronously. This keeps the first iteration simple and makes parser output easy to inspect.

Later iterations should move long-running parses behind a job table and background worker.

