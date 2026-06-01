# Dispatch Handoff

v1.5 makes the queue mandatory. The API no longer parses or stores documents in
the request path. Each uploaded file creates a persisted job, parser workers
produce a full parsed document result, and the dispatcher decides whether to
store local artifacts, index Elastic documents, or do both.

The queue is process-local for the MVP. It does not require Redis, Celery,
Kafka, or another queue service. Persisted job state is used for status
visibility and startup recovery.

## Flow

```mermaid
sequenceDiagram
    participant API as "FastAPI / FileIngestionService"
    participant Jobs as "SQLite jobs"
    participant Parser as "Parser worker pool"
    participant Queue as "Full-document dispatch queue"
    participant Dispatch as "Dispatcher service thread"
    participant Local as "Local artifact sink"
    participant Elastic as "Elasticsearch helpers.bulk"

    API->>Jobs: "Create job per file: parser_queued"
    Parser->>Jobs: "status = parsing"
    Parser->>Queue: "Enqueue full ParseOutput + chunks + embedding records"
    Parser->>Jobs: "status = dispatch_queued"
    Dispatch->>Queue: "Take up to dispatch_max_bulk_size documents"
    Dispatch->>Jobs: "status = dispatching"
    opt "local or local_and_elastic"
        Dispatch->>Local: "Write normalized, markdown, chunks, embedding JSONL"
        Dispatch->>Jobs: "status = stored_local"
    end
    opt "elastic or local_and_elastic"
        Dispatch->>Elastic: "Bulk one item per chunk"
        Elastic-->>Dispatch: "bulk success or item errors"
    end
    Dispatch->>Jobs: "status = completed or failed"
```

## Statuses

| Status | Meaning |
| --- | --- |
| `parser_queued` | The upload is stored and waiting for a parser worker. |
| `parsing` | A parser worker is running Docling or another parser. |
| `parsed` | Parser output exists in memory and is ready to enter the dispatch queue. |
| `dispatch_queued` | The full parsed result is waiting for the dispatcher. |
| `dispatching` | The dispatcher selected the document for the current batch. |
| `stored_local` | Local artifacts were written successfully. |
| `indexed_elastic` | Reserved for Elastic-only progress reporting. |
| `retryable_failure` | A queue or dispatch failure can be retried by recovery or operator action. |
| `completed` | All configured sinks finished successfully. |
| `failed` | Parsing, local storage, or Elastic dispatch failed after retry handling. |

## Configuration

```bash
export INGEST_PARSER_WORKER_COUNT=2
export INGEST_DISPATCH_QUEUE_MAX_SIZE=100
export INGEST_DISPATCH_QUEUE_MAX_PAYLOAD_BYTES=
export INGEST_DISPATCH_MAX_BULK_SIZE=5
export INGEST_DISPATCH_IDLE_INTERVAL_SECONDS=0.5
export INGEST_DISPATCH_SINK_MODE=local
export INGEST_DISPATCH_MAX_RETRIES=3
export INGEST_EMBEDDING_ELASTIC_URL="https://your-elastic-endpoint:9200"
export INGEST_EMBEDDING_ELASTIC_USERNAME="your-user"
export INGEST_EMBEDDING_ELASTIC_PASSWORD="your-password"
export INGEST_EMBEDDING_ELASTIC_INDEX="open-rag-embeddings-v2"
export INGEST_EMBEDDING_ELASTIC_MAPPING_VERSION="v2"
export INGEST_EMBEDDING_ELASTIC_PIPELINE=
```

`INGEST_DISPATCH_SINK_MODE` accepts:

- `local`: write local artifacts only.
- `elastic`: index Elastic chunk documents only.
- `local_and_elastic`: do both.

Do not commit real credentials. The checked-in env files contain placeholders
only.

## Elasticsearch Contract

The dispatcher uses the official `elasticsearch` 9.x Python client and
`elasticsearch.helpers.bulk`. Queue items are full parsed documents, not chunk
records. The dispatcher generates one Elastic bulk action per RAG chunk and
uses deterministic `_id = record_id` so retries are idempotent.

`INGEST_DISPATCH_QUEUE_MAX_SIZE` bounds queue depth. Set
`INGEST_DISPATCH_QUEUE_MAX_PAYLOAD_BYTES` when the process should reject a
single oversized parsed document instead of keeping a very large in-memory
payload. The MVP queue is still process-local; for multi-process API servers or
hard durability across restarts, replace it with an external queue or persisted
spool in a future version.

The dispatcher sends a lean chunk document to Elasticsearch. Each indexed chunk
contains the stable fields needed for RAG retrieval and filtering:
`record_id`, `document_id`, `chunk_id`, `content`, `title`,
`source_file_name`, `input_format`, `parser`, `pipeline`, `chunking_strategy`,
page span, element types, and confidence scores. Full Docling metadata,
runtime diagnostics, provenance boxes, local paths, and raw duplicate text stay
in the local document artifacts instead of being repeated in every indexed
chunk.

For `INGEST_EMBEDDING_ELASTIC_MAPPING_VERSION=v1`, the configured ingest
pipeline embeds `content` and `title` into `content_embedding` and
`title_embedding`. The v1 index `_source` excludes the generated vector fields.

For `INGEST_EMBEDDING_ELASTIC_MAPPING_VERSION=v2`, the v2 index sets
`index.default_pipeline=open_rag_embeddings_v2_semantic_pipeline`, so
Elasticsearch automatically runs the pipeline for normal bulk indexing
requests. That pipeline copies `content` into `content_semantic` and `title`
into `title_semantic`; those `semantic_text` fields run inference through their
field mapping. The index keeps `content_semantic` and `title_semantic` in
`_source` so search and debug responses can show the text sent to inference.

The v2 asset at `elastic/open-rag-embeddings-v2.json` contains the index
mapping, the index default-pipeline setting, and the ingest pipeline. Create the
pipeline before the index:

```bash
python - <<'PY'
import json
from pathlib import Path

asset = json.loads(Path("elastic/open-rag-embeddings-v2.json").read_text())
Path("/tmp/open-rag-embeddings-v2-index.json").write_text(json.dumps(asset["index"]))
Path("/tmp/open-rag-embeddings-v2-pipeline.json").write_text(json.dumps(asset["pipeline"]))
print(asset["index_name"])
print(asset["pipeline_name"])
PY

curl -k -u "$ELASTIC_USER:$ELASTIC_PASS" \
  -H "Content-Type: application/json" \
  -X PUT "$ELASTIC_URL/_ingest/pipeline/open_rag_embeddings_v2_semantic_pipeline" \
  --data-binary @/tmp/open-rag-embeddings-v2-pipeline.json

curl -k -u "$ELASTIC_USER:$ELASTIC_PASS" \
  -H "Content-Type: application/json" \
  -X PUT "$ELASTIC_URL/open-rag-embeddings-v2" \
  --data-binary @/tmp/open-rag-embeddings-v2-index.json
```

The Elastic payload does not include local filesystem paths. Local paths remain
available in the service's local output directory and job metadata.

## Public API Contract

The queue is internal to ingestion. There are no public queue API endpoints.

```text
POST /v1/ingest/file or /v1/ingest/files
-> job DB row per file
-> parser worker pool
-> mandatory full-document dispatch queue
-> dispatcher-owned local storage and/or Elastic bulk indexing
```

Use the job endpoint to observe state:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}"
```

Local storage remains the canonical per-document artifact store when the local
sink is enabled. Elasticsearch receives one indexed document per RAG chunk.
