# Docling Engine Lifecycle

This service keeps Docling engines alive across API ingestion jobs so Docling
pipeline state is not rebuilt once per document. The implementation follows Docling's
`DocumentConverter` API:

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
TTL, and Docling page batching uses the backend constant `32`.

Docling conversion concurrency is derived from `INGEST_PARSER_WORKER_COUNT`, so
the parser queue pool is the single document-level backpressure setting.

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

Expected behavior for repeated compatible PDF jobs is reuse of idle cached
engines. Concurrent compatible jobs can create up to
`INGEST_PARSER_WORKER_COUNT` engines for the same key so each active job has
isolated converter state.

## Tuning

- Dramatiq parser workers should use one process per GPU and
  `--threads ${INGEST_PARSER_WORKER_COUNT:-2}`. Multiple processes each create
  their own Docling engine pool and can multiply GPU memory use.
- Parser actors use `INGEST_DRAMATIQ_PARSER_TIME_LIMIT_MS`; keep it above the
  worst-case Docling OCR duration for large PDFs. The default is 4 hours to
  avoid interrupting Docling's internal stage threads mid-conversion. Restart
  both the API publisher process and the Dramatiq worker after changing this
  value because queued messages carry their Dramatiq options.
- Parser failures are marked `retrying` and republished at the parser queue tail
  until `INGEST_PARSER_MAX_RETRY_ATTEMPTS` is exhausted.
- Increase `INGEST_PARSER_WORKER_COUNT` to allow more queued documents to make
  Docling progress concurrently in one process.
- Reduce `INGEST_PARSER_WORKER_COUNT` when GPU memory or the RemoteLLM endpoint
  needs stronger backpressure.
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

RemoteLLM request concurrency follows `INGEST_PARSER_WORKER_COUNT`. Size the
remote inference server for the selected parser worker count and reduce parser
threads when the endpoint needs stronger backpressure.
