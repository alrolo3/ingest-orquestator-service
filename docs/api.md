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

- `parser`: currently only `docling`.
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

