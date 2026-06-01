# Architecture

The MVP mirrors the ingestion side of a RAG pipeline without taking on retrieval infrastructure.

For a Mermaid diagram view, see [Architecture Diagram](architecture-diagram.md).

```text
FastAPI
-> application service
-> parser worker pool
-> mandatory full-document dispatch queue
-> dispatcher-owned storage and sink ports
-> Docling and filesystem adapters
-> normalized document models
-> chunks, embedding records, local output files, and optional Elastic bulk indexing
```

## Boundaries

- `api/` contains FastAPI app creation, route modules, and dependency wiring.
- `application/` contains use cases, parser registry, exceptions, and ports.
- `models/` contains one Pydantic model per file.
- `normalizers/docling/` maps Docling dictionaries into project-owned models.
- `infrastructure/docling/` adapts Docling into the `DocumentParser` port.
- `infrastructure/filesystem/` stores uploads and writes parser artifacts.
- `infrastructure/sqlite/` persists ingestion job state.
- `infrastructure/elastic/` submits dispatcher batches through the official Elasticsearch Python client bulk helper.
- `main.py` only exposes the ASGI `app` for Uvicorn.

## Project Shape

```text
src/ingest_orquestator_server/
├── api/
│   ├── app.py
│   ├── dependencies.py
│   └── routes/
├── application/
│   ├── ports/
│   └── services/
├── config/
├── infrastructure/
│   ├── docling/
│   ├── elastic/
│   └── filesystem/
├── models/
└── normalizers/
    └── docling/
```

## Current MVP Behavior

The API is asynchronous. Upload requests create one persisted job per file and
return immediately with `parser_queued` status. Parser queue concurrency is
configured as independent parser processes; each process runs one document parse
workflow and can use Docling's internal per-document concurrency before
enqueuing the full parsed document result in the mandatory dispatch queue.

`ParsedDocumentDispatchService` is the dispatcher coordinator. It drains up to the
configured number of parsed-document dispatch items per batch, stores local
artifacts when the local sink is enabled, and sends Elastic bulk requests when
the Elastic sink is enabled. Elastic payload generation consumes the unified RAG
ingestion records carried by the dispatch item: each chunk record is indexed as
one Elasticsearch document with deterministic `_id = record_id`. If chunking is
disabled, one document-level RAG record is indexed instead. Bulk failures are
retried and then persisted as `failed` when retry budget is exhausted.

## Adding A Parser

To add another parser backend, such as MinerU:

1. Add an infrastructure adapter that implements `application.ports.DocumentParser`.
2. Add a normalizer package that converts parser-native output into `ParsedDocument`, `DocumentPage`, and `DocumentElement`.
3. Register the parser in `infrastructure/parser/parser_registry_factory.py`.
4. Add parser-specific settings in `config/settings.py`.
5. Add parser contract tests under `tests/contracts/`.
6. Document runtime dependencies and Docker overrides if the parser needs a special GPU image.

## Docling Pipeline Extension

Docling integration is built around `DocumentConverter`. The converter factory
chooses allowed formats and per-format options. `standard` mode is supported for
all configured formats; direct `vlm` mode is supported for PDF and image inputs.

The parser keeps Docling `ConversionResult` metadata, including status, errors,
timings, and confidence reports, only long enough to build the minimal parsed
content. The default local artifacts are `document.md`,
`document_metadata.json`, and `rag_chunks.jsonl`; `document.html` is written only
when requested through the API. The public runtime interface is the FastAPI
server.
