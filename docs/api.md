# API

## Health

```http
GET /health
```

Returns the service name and status.

## Ingest File

```http
POST /v1/ingest/file
```

Multipart form fields:

- `file`: document to parse.

Query parameters:

- `parser`: parser backend to use. The default is `docling`.
- `pipeline`: optional Docling pipeline override. Supported values are
  `standard`, `vlm`, and `auto`. When omitted, the configured profile/default
  pipeline is used.
- `profile`: optional ingestion profile. Supported values are `rag_ready`,
  `parse_only`, `ocr_only`, `standard_enriched`, and `vlm`.
- `chunking_enabled`: optional request-level chunking override.
- `chunking_strategy`: optional request-level strategy override. Supported
  values are `hybrid`, `line_based`, and `legacy_char`.
- `async_mode`: defaults to `false`; when `true`, the API returns a queued job
  immediately and parses the file in an in-process background task.
- `include_document`: defaults to `true`; when `false`, the response returns file paths only.

Example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?include_document=false&pipeline=standard" \
  -F "file=@/path/to/document.pdf"
```

Async example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?async_mode=true" \
  -F "file=@/path/to/document.pdf"
```

Successful responses include:

- `job_id`
- `status`
- `parser`
- `document_id`
- output file paths
- optionally the normalized parsed document
- optionally generated chunks

`pipeline=vlm` is supported directly for PDF and image inputs. Other
Docling formats use `pipeline=standard`.

Use `profile=parse_only&chunking_enabled=false` when a downstream embedding
store will do its own chunking.

## Get Job

```http
GET /v1/ingest/jobs/{job_id}
```

Returns persisted job metadata, including status, parser, input path, output paths, timestamps, and error details.

## List Outputs

```http
GET /v1/ingest/jobs/{job_id}/outputs
```

Returns output artifact paths for a completed job.

## Download Output

```http
GET /v1/ingest/jobs/{job_id}/outputs/{output_type}
```

Supported `output_type` values:

- `manifest`
- `normalized`
- `markdown`
- `text`
- `raw`
- `html`
- `chunks`
- `embedding`
- `confidence`

Examples:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/chunks"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/confidence"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/normalized"
```
