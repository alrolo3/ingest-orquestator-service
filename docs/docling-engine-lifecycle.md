# Docling Engine Lifecycle

This service keeps Docling engines alive across API ingestion jobs so GPU models
are not loaded once per document. The implementation follows Docling's
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

The GPU env files keep engine caching enabled:

```bash
INGEST_DOCLING_ENGINE_CACHE_ENABLED=true
INGEST_DOCLING_ENGINE_IDLE_TTL_SECONDS=0
INGEST_DOCLING_PARSE_CONCURRENCY=2
INGEST_DOCLING_GPU_ENGINE_CONCURRENCY=1
INGEST_DOCLING_GPU_BATCH_MAX_DOCUMENTS=5
INGEST_DOCLING_GPU_BATCH_WAIT_MS=250
INGEST_DOCLING_PERF_PAGE_BATCH_SIZE=32
```

For Qwen3 VLM and picture descriptions, the GPU env uses `remote_llm` so the
large model lives in a separate OpenAI-compatible inference server instead of
inside each API worker:

```bash
INGEST_DOCLING_VLM_RUNTIME=remote_llm
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_RUNTIME=remote_llm
INGEST_DOCLING_REMOTE_LLM_URL=http://localhost:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

## Optional Warmup

Warmup is disabled by default because it makes API startup heavier. Enable it
when the GPU server should load the common pipeline before the first upload:

```bash
INGEST_DOCLING_ENGINE_WARMUP_ENABLED=true
INGEST_DOCLING_ENGINE_WARMUP_FORMATS=pdf
```

Warmup uses the configured default pipeline. For a standard RAG pipeline with
OCR and picture descriptions enabled, warming `pdf` may initialize several
models.

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
`INGEST_DOCLING_PARSE_CONCURRENCY` engines for the same key so each active job
has isolated converter state.

## Tuning

- Dramatiq parser workers should use one process per GPU and
  `--threads ${INGEST_PARSER_WORKER_COUNT:-2}`. Multiple processes each create
  their own Docling engine pool and can multiply GPU memory use.
- Increase `INGEST_PARSER_WORKER_COUNT` to accept more queued API work in a
  process.
- Set `INGEST_DOCLING_PARSE_CONCURRENCY` to the number of Docling conversions
  allowed to make progress at the same time. Leave it unset to match
  `INGEST_PARSER_WORKER_COUNT`, or set it lower when GPU memory or the
  RemoteLLM endpoint needs stronger backpressure.
- Keep `INGEST_DOCLING_GPU_ENGINE_CONCURRENCY=1`. Queued parsing leases one
  converter per active job instead of making concurrent calls against the same
  converter.
- `INGEST_DOCLING_GPU_BATCH_MAX_DOCUMENTS` and
  `INGEST_DOCLING_GPU_BATCH_WAIT_MS` are legacy explicit-batch settings.
  Independent queued jobs are no longer batched together because progress must
  stay accurate per job.
- Keep `INGEST_DOCLING_ENGINE_IDLE_TTL_SECONDS=0` on dedicated GPU servers to
  avoid unloading models between jobs.

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

Tune `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY` for per-conversion page requests,
then tune `INGEST_DOCLING_PARSE_CONCURRENCY` for document-level concurrency.
The remote inference server must be sized for the product of those two values.
