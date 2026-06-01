# Spec: Ingestor Settings Panel

## Objective

Move runtime-safe `INGEST_` service settings from env-only configuration into a persistent admin surface named "Ingestor settings". Operators can change settings such as Docling accelerator device, parser/model defaults, upload limits, chunking defaults, dispatch sink settings, and RemoteLLM/Elastic options before submitting documents. Settings persist in SQLite and become part of the effective `Settings` object used by API dependencies before parser models are loaded.

## Tech Stack

- Backend: FastAPI, Pydantic v2, pydantic-settings, sqlite3.
- Frontend: React, TypeScript, Vite, Vitest, lucide-react.
- Persistence: new `ingestor_settings` table in the existing SQLite runtime database derived from `INGEST_STORAGE_DIR`.

## Commands

- Backend tests: `.venv/bin/python -m pytest -q`
- Backend lint: `ruff check .`
- Frontend lint: `cd src/frontend && npm run lint`
- Frontend tests: `cd src/frontend && npm test`
- Frontend build: `cd src/frontend && npm run build`
- Dev backend: `python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000`
- Dev frontend: `cd src/frontend && npm run dev`

## Project Structure

- `src/ingest_orquestator_server/config/settings.py`: base env-backed settings model.
- `src/ingest_orquestator_server/application/services/`: effective settings and validation logic.
- `src/ingest_orquestator_server/infrastructure/sqlite/`: SQLite table/repository implementation.
- `src/ingest_orquestator_server/api/routes/`: settings API endpoints.
- `src/frontend/src/`: settings API client and React settings view.
- `tests/` and `src/frontend/src/*.test.*`: backend and frontend regression tests.

## Code Style

```python
def get_effective_settings(
    base_settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[IngestorSettingsRepository, Depends(get_ingestor_settings_repository)],
) -> Settings:
    return IngestorSettingsService(base_settings, repository).effective_settings()
```

Use existing dependency-injection and Pydantic validation patterns. Store structured values as JSON and use parameterized SQLite queries only.

## Testing Strategy

- Backend unit tests prove settings are persisted, validated, reset, and redacted.
- API tests prove `/v1/ingest/settings` and `/v1/ingest/capabilities` use SQLite overrides.
- Frontend tests prove the new navigation view renders settings and saves changed values.

## Boundaries

- Always: validate all setting updates with the existing `Settings` model; redact secret values in GET responses; refresh capabilities after settings saves.
- Ask first: changing boot-time settings from the frontend, adding authentication, or adding new dependencies.
- Never: return stored secrets to the browser; concatenate user input into SQL; silently remove existing env support.

## Runtime-Configurable Scope

Runtime-configurable by default: all `Settings.model_fields` except boot-time-only fields.

Boot-time-only fields: `storage_dir`, `cors_allow_origins`, `queue_backend`, `rabbitmq_url`, `dramatiq_parser_queue_name`, `dramatiq_dispatch_queue_name`, `dramatiq_parser_time_limit_ms`, `dramatiq_dispatch_time_limit_ms`, `parser_process_count`, `parser_threads_per_process`, and deprecated `parser_worker_count`.

Secrets: `docling_remote_llm_api_key` and `embedding_elastic_password` are write-only in the frontend/API response.

## Success Criteria

- A new frontend view named "Ingestor settings" can load, edit, save, and reset runtime settings.
- Saved settings survive process restarts because they are stored in SQLite.
- Updating `docling_accelerator_device` changes the effective settings used by parser dependencies before new model loads.
- Existing env vars remain the fallback when no SQLite override exists.
- Backend and frontend validation commands pass.
