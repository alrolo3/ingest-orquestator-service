# Docling Engine Lifecycle

This service keeps Docling engines alive across API ingestion jobs so GPU models
are not loaded once per document. The implementation follows Docling's
`DocumentConverter` API:

- `DocumentConverter.initialize_pipeline(format)` is used for optional warmup.
- `DocumentConverter.convert(source)` is used for one document.
- `DocumentConverter.convert_all(sources)` is used when compatible jobs can be
  batched.
- `DocumentConverter` exposes initialized pipelines internally, so one cached
  converter is the reuse boundary for a format and pipeline configuration.

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
- `engines[].initialize_count`: how many times the pipeline initialized.
- `engines[].conversion_count`: number of documents converted by the engine.
- `engines[].batch_conversion_count`: number of `convert_all(...)` calls.
- `engines[].last_cuda_memory`: GPU memory snapshot when PyTorch is available.

Expected behavior for repeated compatible PDF jobs is one engine and one
pipeline initialization, with `conversion_count` increasing over time.

## Tuning

- Increase `INGEST_PARSER_WORKER_COUNT` to accept more queued API work.
- Keep `INGEST_DOCLING_GPU_ENGINE_CONCURRENCY=1` until the configured Docling
  pipeline is proven safe with concurrent calls against the same converter.
- Increase `INGEST_DOCLING_GPU_BATCH_MAX_DOCUMENTS` only if documents arrive in
  bursts and GPU memory is stable.
- Use `INGEST_DOCLING_GPU_BATCH_WAIT_MS=0` to disable scheduler batching when
  low single-document latency matters more than throughput.
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
