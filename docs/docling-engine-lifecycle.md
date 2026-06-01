# Docling Engine Lifecycle

Each parser process owns its Docling engine instances. The API process does not
construct parser engines before forking or spawning parser jobs. Within a parser
process, Docling pipeline state can be reused for that process and document
workflow. The implementation follows Docling's `DocumentConverter` API:

- `DocumentConverter.initialize_pipeline(format)` is used for optional warmup.
- `DocumentConverter.convert(source)` is used for one document.
- `DocumentConverter.convert_all(sources)` is reserved for explicit batch parse
  calls; independent queued jobs are not coalesced because each job needs
  isolated progress.
- `DocumentConverter` exposes initialized pipelines internally, so one cached
  converter is the reuse boundary for one active parse slot.

## Engine Key

An engine is keyed by:

- Docling input format, such as `pdf`, `image`, or `md`.
- Resolved pipeline, such as `standard` or `vlm`.
- Effective Docling option metadata.

If any relevant setting changes, the API creates a new engine instead of
reusing a stale one.

## GPU Defaults

The GPU env files keep only deployment-specific Docling values. Engine caching
is always enabled, warmup is disabled, cached engines are not evicted by idle
TTL, and Docling threaded pipeline batch sizes are explicit settings.

Queue-level document concurrency is controlled by `INGEST_PARSER_PROCESS_COUNT`.
Docling's own internal per-document concurrency is controlled through settings
such as `INGEST_DOCLING_PDF_OCR_BATCH_SIZE`,
`INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE`, and
`INGEST_DOCLING_PDF_TABLE_BATCH_SIZE`.

For Qwen3 VLM and picture descriptions, the GPU env uses RemoteLLM so the large
model lives in a separate OpenAI-compatible inference server instead of inside
each API worker:

```bash
INGEST_DOCLING_REMOTE_LLM_URL=http://localhost:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

## Warmup

Warmup is disabled in backend constants because it makes API startup heavier.
The first compatible upload initializes the configured pipeline.

## Diagnostics

Use the diagnostics endpoint to confirm engine reuse:

```bash
curl -s http://127.0.0.1:8000/v1/ingest/docling/engines | python -m json.tool
```

Useful fields:

- `engine_count`: number of cached Docling engines.
- `parse_concurrency`: maximum active Docling conversions in this process.
- `leased_engine_count`: active conversions currently holding cached engines.
- `engines[].initialize_count`: how many times the pipeline initialized.
- `engines[].conversion_count`: number of documents converted by the engine.
- `engines[].batch_conversion_count`: number of `convert_all(...)` calls.
- `engines[].last_cuda_memory`: GPU memory snapshot when PyTorch is available.

Expected behavior for repeated compatible PDF jobs inside one parser process is
reuse of idle cached engines. Concurrent parser processes each create their own
engine pool, so memory use scales with `INGEST_PARSER_PROCESS_COUNT`.

## Tuning

- Dramatiq parser workers should run with explicit process concurrency and one
  actor thread per parser process:
  `--processes ${INGEST_PARSER_PROCESS_COUNT:-2}` and
  `--threads ${INGEST_PARSER_THREADS_PER_PROCESS:-1}`. Each process creates its
  own Docling engine pool and can multiply GPU memory use.
- Parser actors use `INGEST_DRAMATIQ_PARSER_TIME_LIMIT_MS`; keep it above the
  worst-case Docling OCR duration for large PDFs. The default is 4 hours to
  avoid interrupting Docling's internal stage threads mid-conversion. Restart
  both the API publisher process and the Dramatiq worker after changing this
  value because queued messages carry their Dramatiq options.
- Parser failures are marked `retrying` and republished at the parser queue tail
  until `INGEST_PARSER_MAX_RETRY_ATTEMPTS` is exhausted.
- Increase `INGEST_PARSER_PROCESS_COUNT` to allow more queued documents to make
  Docling progress concurrently across processes.
- Reduce `INGEST_PARSER_PROCESS_COUNT` when GPU memory needs stronger
  backpressure. Reduce `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY` when the remote
  inference endpoint is the bottleneck.
- Queued parsing leases one converter per active job instead of making
  concurrent calls against the same converter.

## RemoteLLM Server

Start a vLLM server separately for Qwen3 before using `remote_llm`:

```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --max-num-seqs 64 \
  --max-num-batched-tokens 8192 \
  --enable-chunked-prefill \
  --gpu-memory-utilization 0.9
```

Then start this API with `.env` or `env-cuda-gpu`. The API sends Docling VLM
requests to `INGEST_DOCLING_REMOTE_LLM_URL`; it does not load Qwen3 in each
parser worker when the runtime is `remote_llm`.

RemoteLLM request concurrency follows `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY`.
Size the remote inference server for that value and lower it when the endpoint
needs stronger backpressure. This remains a remote mode; parser processes do not
load a local VLM unless a future parser implementation explicitly adds one.
