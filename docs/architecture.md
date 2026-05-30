# Architecture

The MVP mirrors the ingestion side of a RAG pipeline without taking on retrieval infrastructure.

```text
FastAPI or CLI
-> application service
-> parser/output/storage ports
-> Docling and filesystem adapters
-> normalized document models
-> local output files
```

## Boundaries

- `api/` contains FastAPI app creation, route modules, and dependency wiring.
- `application/` contains use cases, parser registry, exceptions, and ports.
- `models/` contains one Pydantic model per file.
- `normalizers/docling/` maps Docling dictionaries into project-owned models.
- `infrastructure/docling/` adapts Docling into the `DocumentParser` port.
- `infrastructure/filesystem/` stores uploads and writes parser artifacts.
- `cli/` contains the Typer app and command modules.
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
├── cli/
│   └── commands/
├── config/
├── infrastructure/
│   ├── docling/
│   └── filesystem/
├── models/
└── normalizers/
    └── docling/
```

## Current MVP Behavior

The service runs parsing synchronously. This keeps the first iteration simple and makes parser output easy to inspect.

Later iterations should move long-running parses behind a job table and background worker.
