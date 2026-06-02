# API

## Health

```http
GET /health
```

Returns the service name and status.

```http
GET /health/remote-llm
```

Posts a minimal OpenAI-compatible chat completion request to the configured
RemoteLLM endpoint and returns `ok`, `url`, `model`, `status_code`, and `error`.
Use this before `pipeline=vlm` tests to verify the external VLM endpoint.

## Ingestion Capabilities

```http
GET /v1/ingest/capabilities
```

Returns UI-safe ingestion option metadata:

- allowed upload extensions and max upload size.
- supported parsers and pipelines.
- parser-specific chunking defaults and supported chunking strategies.
- runtime metadata such as sink mode, OCR engine, VLM model, and Elastic index.
- output artifact types and job statuses.

Secrets such as Elastic passwords and RemoteLLM API keys are never returned.

Example:

```bash
curl "http://127.0.0.1:8000/v1/ingest/capabilities" | python -m json.tool
```

## Ingest File

The preferred GUI contract is the document/run API below. The older
`/v1/ingest/file`, `/v1/ingest/files`, and `/v1/ingest/jobs` endpoints remain
supported compatibility endpoints for scripts and existing clients.

```http
POST /v1/ingest/file
```

Multipart form fields:

- `file`: document to parse.

Query parameters:

- `parser`: parser backend to use. The default is `docling`.
- `pipeline`: optional Docling pipeline override. Supported values are
  `standard`, `vlm`, and `auto`. When omitted, the configured default pipeline
  is used.
- `chunking_enabled`: optional request-level chunking override.
- `chunking_strategy`: optional request-level strategy override. Supported
  values are parser-specific and discoverable from `/v1/ingest/capabilities`.
  Docling currently exposes `token` and `page`; `line` is a platform strategy
  name but is not implemented for Docling yet.
- `ocr_languages`: optional comma-separated OCR language list. OCR is always
  enabled and defaults to `en`.
- `async_mode`: deprecated compatibility parameter. In v1.5 all ingest calls
  are asynchronous and return a job immediately.
- `include_document`: deprecated compatibility parameter. Parsed documents are
  retrieved through job output endpoints after dispatch stores local artifacts.

Example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/path/to/document.pdf"
```

Batch example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/files?pipeline=standard" \
  -F "files=@/path/to/first.pdf" \
  -F "files=@/path/to/second.pdf"
```

Successful responses include:

- `job_id`
- `status`
- `source_file_name`
- `status_url`
- `outputs_url`
- `parser`
- `document_id`
- local output file paths after the dispatcher stores artifacts

For async job creation, `outputs` is usually `null` in the immediate response.
Use `status_url` to poll the job and `outputs_url` after the job reaches
`completed`.

`pipeline=vlm` is supported directly for PDF and image inputs. Other
Docling formats use `pipeline=standard`.

Use `chunking_enabled=false` when a downstream embedding store will do its own
chunking. Use the selected parser's capability entry before sending
`chunking_strategy`.

In v1.5, ingestion always uses the internal queue. The status starts as
`parser_queued`, then progresses through `parsing`, `parsed`, `dispatch_queued`,
`dispatching`, `stored_local` and/or `indexed_elastic`, and finally `completed`
or `failed`. Transient queue or sink pressure can surface as
`retryable_failure`. The queue is internal; callers do not call a queue
endpoint. Use the job API to observe the current state.

## Document and Run API

Use documents for stable uploaded content and runs for individual parse
attempts. Uploading the same file content with different pipelines returns the
same `document_id` and a new run, which lets the GUI show standard and VLM
attempts together.

```http
POST /v1/ingest/documents
```

Multipart form fields:

- `files`: one or more uploaded documents.

Query parameters match `/v1/ingest/files`: `parser`, `pipeline`,
`chunking_enabled`, `chunking_strategy`, `dispatch_sink_mode`, `ocr_languages`,
and `include_html`.

Example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/documents?pipeline=standard" \
  -F "files=@/path/to/document.pdf"
```

The response contains document envelopes:

- `document`: stable content identity with `document_id`, `content_hash`,
  source file name, size, MIME type, and timestamps.
- `latest_run`: the newest parse attempt for the document.
- `runs`: compact run history ordered newest first.

Create a new parse attempt for an existing document:

```http
POST /v1/ingest/documents/{document_id}/runs
```

Example:

```bash
curl -X POST \
  "http://127.0.0.1:8000/v1/ingest/documents/{document_id}/runs?pipeline=vlm"
```

List documents with bounded pagination:

```http
GET /v1/ingest/documents?limit=20&cursor=0&status=completed&q=invoice
```

Fetch one document envelope:

```http
GET /v1/ingest/documents/{document_id}
```

Poll runs in one batch:

```http
GET /v1/ingest/runs?ids={run_id_1},{run_id_2}
```

Fetch one run:

```http
GET /v1/ingest/runs/{run_id}
```

List run outputs:

```http
GET /v1/ingest/runs/{run_id}/outputs
```

## Get Job

```http
GET /v1/ingest/jobs/{job_id}
```

Returns persisted job metadata, including status, parser, input path, output paths, timestamps, and error details.
While a document is parsing, `metadata.progress` contains the latest Docling
stage, page totals, completed pages, remaining pages, and percent complete when
page counts are available. `metadata.progress_history` keeps the recent bounded
history of those updates.

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

## Frontend

The browser app lives in `src/frontend`. See
[`docs/frontend.md`](frontend.md) for install, development, and build commands.
