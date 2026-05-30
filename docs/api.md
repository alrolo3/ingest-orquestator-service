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
- `include_document`: defaults to `true`; when `false`, the response returns file paths only.

Example:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?include_document=false" \
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

Examples:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/chunks"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/normalized"
```
