# Spec: Ingestion API Job and Document Rework

## Objective

Rework the ingestion API so the GUI can render a stable document view with multiple parse attempts, clear pipeline/runtime traceability, and efficient polling. The immediate production bug is that VLM PDF conversion must not use Docling's threaded PDF backend, because Docling's VLM pipeline still requires ordered/random page access. The broader product issue is that each upload is currently represented only as an independent job, so uploading the same file through standard and then VLM creates separate rows with no durable document identity for the UI to group by.

## Assumptions

- Keep existing `/v1/ingest/file`, `/v1/ingest/files`, and `/v1/ingest/jobs` compatible while introducing clearer v2-style response objects under `/v1/ingest`.
- Compute a content identity for uploads from a file hash, not from filename alone.
- Model a document as the stable uploaded content and a job/run as one parse attempt with parser, pipeline, chunking, dispatch, and runtime metadata.
- Keep orchestration logic in application services; routes remain validation and transport adapters.
- Preserve local artifact output paths while adding richer metadata around attempts and outputs.

## Proposed API Shape

- `POST /v1/ingest/documents`: upload one or more files and return document envelopes with latest run summaries.
- `POST /v1/ingest/documents/{document_id}/runs`: create a new parse attempt for an existing document with different parser/pipeline/options.
- `GET /v1/ingest/documents?status=&q=&limit=&cursor=`: paginated document list for the GUI.
- `GET /v1/ingest/documents/{document_id}`: document envelope with current/latest run plus compact run history.
- `GET /v1/ingest/runs?ids=...`: batch poll run updates, replacing wide repeated job fetches.
- `GET /v1/ingest/runs/{run_id}`: detailed run state, progress timeline, error, options, and output links.
- `GET /v1/ingest/runs/{run_id}/outputs`: run-scoped artifacts.

## Data Model

- `ingestion_documents`: `document_id`, `content_hash`, `source_file_name`, `size_bytes`, `mime_type`, `storage_path`, `created_at`, `updated_at`.
- `ingestion_runs`: current job fields plus `run_id`, `document_id`, `attempt_number`, `parser`, `pipeline`, `options_json`, `runtime_json`, `status`, `error`, timestamps, and output summary.
- `ingestion_run_events`: append-only progress/error/status events for traceability and GUI timelines.

## Compatibility and Migration

- Treat current `ingestion_jobs` rows as legacy runs during migration.
- Add read adapters so old job endpoints continue to return `IngestionJob`.
- Introduce deprecation notices in docs only after the GUI has moved to document/run endpoints.
- Do not delete old endpoints until metrics or logs show zero active clients.

## Security

- Validate all query parameters and request options at API boundaries.
- Never return filesystem paths that are not already part of the current artifact contract.
- Do not expose stack traces or internal Docling exception details directly in public error messages; keep detailed traces in run events/logs.
- Keep upload validation based on configured extension/size rules and add content hash computation while streaming, not by loading full files into memory.

## Performance

- Every collection endpoint must be paginated.
- Polling endpoints should return compact run summaries, not full documents or artifacts.
- Add repository indexes for `document_id`, `content_hash`, `status`, and `updated_at`.
- Avoid N+1 repository calls in document list responses by querying latest run summaries in batch.

## Task Breakdown

### Task 1: Fix VLM PDF Backend Selection

- Acceptance: VLM PDF routes use `DoclingParseDocumentBackend`; standard PDF routes keep `ThreadedDoclingParseDocumentBackend`.
- Verify: `.venv/bin/python -m pytest tests/test_docling_format_routes.py tests/test_docling_converter_factory.py -q`.

### Task 2: Add Document/Run Read Models

- Acceptance: new Pydantic response models represent document envelopes, run summaries, progress events, and output links.
- Verify: model unit tests cover standard success, VLM failure, and multiple runs for the same document.

### Task 3: Add Repository Contract and SQLite Migration

- Acceptance: repository can upsert documents by content hash, create runs, list documents with latest run summaries, and batch-get runs by id.
- Verify: SQLite repository tests cover migration from an empty database and query pagination.

### Task 4: Add Document/Run Application Services

- Acceptance: upload creates or reuses document records and creates a run for each requested parse.
- Verify: service tests prove standard then VLM on the same file returns one document with two runs.

### Task 5: Add New API Endpoints

- Acceptance: routes return closed, GUI-ready document/run objects without route-level business logic.
- Verify: FastAPI tests cover upload, re-run, paginated list, batch poll, and output lookup.

### Task 6: Update Frontend State Model

- Acceptance: GUI groups repeated uploads by document and shows run history with pipeline/status/error per attempt.
- Verify: frontend unit tests cover standard success followed by VLM failure without duplicate document cards.

### Task 7: Deprecation and Documentation

- Acceptance: docs explain old job endpoints as compatibility APIs and new document/run endpoints as preferred.
- Verify: backend tests, frontend lint/test/build, and docs reviewed for stale job-only assumptions.

## Validation Gates

- Backend: `.venv/bin/python -m pytest -q`
- Backend lint: `ruff check .`
- Frontend when touched: `cd src/frontend && npm run lint && npm test && npm run build`

## Open Questions

- Should the API deduplicate by content hash globally or only within the current storage directory?
- Should failed validation uploads create document records, or remain rejected run records only?
- Should old `/v1/ingest/jobs` include `document_id` once migration exists, or stay strictly legacy-shaped?
