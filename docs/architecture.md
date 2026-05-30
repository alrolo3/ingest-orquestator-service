# Architecture

The MVP mirrors the ingestion side of a RAG pipeline without taking on retrieval infrastructure.

```text
FastAPI or CLI
-> application service
-> parser/output/storage ports
-> Docling and filesystem adapters
-> normalized document models
-> chunks and local output files
```

## Boundaries

- `api/` contains FastAPI app creation, route modules, and dependency wiring.
- `application/` contains use cases, parser registry, exceptions, and ports.
- `models/` contains one Pydantic model per file.
- `normalizers/docling/` maps Docling dictionaries into project-owned models.
- `infrastructure/docling/` adapts Docling into the `DocumentParser` port.
- `infrastructure/filesystem/` stores uploads and writes parser artifacts.
- `infrastructure/sqlite/` persists ingestion job state.
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

The synchronous flow still persists job state, outputs, diagnostics, and chunks. Later iterations should move long-running parses behind a background worker.

## Adding A Parser

To add another parser backend, such as MinerU:

1. Add an infrastructure adapter that implements `application.ports.DocumentParser`.
2. Add a normalizer package that converts parser-native output into `ParsedDocument`, `DocumentPage`, and `DocumentElement`.
3. Register the parser in `infrastructure/parser/parser_registry_factory.py`.
4. Add parser-specific settings in `config/settings.py`.
5. Add parser contract tests under `tests/contracts/`.
6. Document runtime dependencies and Docker overrides if the parser needs a special GPU image.
