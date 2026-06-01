# Environment Configuration Reference

The service reads configuration from environment variables with the `INGEST_`
prefix. Pydantic also loads a local `.env` file automatically when the process
starts.

Use one of the checked-in environment files as a starting point:

```bash
cp .env.example .env
```

The checked-in environment files contain every `INGEST_` setting as an
assignment, including optional settings. Values that are deployment-specific,
especially Elastic passwords, are placeholders and must be changed in the
untracked local `.env`.

For shell-sourced environments:

```bash
set -a
source env-cpu        # macOS/Linux CPU environment
# or
source env-cuda-gpu   # Linux NVIDIA GPU environment
set +a
```

Quote values that contain spaces when sourcing files in Bash, for example:

```bash
INGEST_DOCLING_VLM_PROMPT="Convert this page to markdown."
```

Comma-separated environment values are decoded by the application for list
settings such as upload extensions, Docling formats, and OCR languages.

## Environment Files

| File | Purpose |
| --- | --- |
| `.env.example` | Same source-safe configuration as `env-cuda-gpu`. Copy it to `.env` for GPU-oriented local development. |
| `env-cpu` | Source-safe CPU environment for macOS and Linux. It avoids external Docling OCR plugins and disables RemoteLLM picture descriptions. |
| `env-cuda-gpu` | Source-safe NVIDIA GPU environment tuned for an A100 80GB class machine. It enables CUDA, SuryaOCR, RemoteLLM VLM stages, higher batch sizes, and larger uploads. |

## Service And Storage

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_SERVICE_NAME` | `ingest-orquestator-server` | `ingest-orquestator-server` | Any string. | Logical service name returned by health/config metadata and useful in logs or deployment labels. |
| `INGEST_STORAGE_DIR` | `.data` | `.data` | Filesystem path. Relative paths are resolved from the process working directory. | Root directory for local runtime state. Uploads, outputs, and SQLite jobs are stored below this path. |
| `INGEST_MAX_UPLOAD_SIZE_MB` | `100` | `2048` | Integer `>= 1`. | Maximum accepted upload size in MiB for API ingestion. Increase for large PDFs or office documents. |
| `INGEST_ALLOWED_UPLOAD_EXTENSIONS` | Multi-format list | `.pdf,.docx,.md` | Comma-separated extensions. Each item can be `.ext` or `ext`; values are normalized to lowercase with a leading dot. | File extensions accepted by upload validation and batch directory discovery. |
| `INGEST_RETENTION_DAYS` | `30` | `30` | Integer `>= 1`. | Default retention window for local runtime artifacts when cleanup is run by an operator or maintenance process. |

## Upload Extension Defaults

The checked-in environment files currently include:

```text
.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.md,.markdown,.txt,.html,.htm,.docx,.pptx,.xlsx,.csv,.json,.adoc,.asciidoc,.tex,.latex,.vtt,.jats,.nxml,.uspto,.xbrl
```

This is the upload gate. Docling allowed formats are derived from these
extensions so upload validation and parser support stay aligned.

## Chunking

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_CHUNKING_ENABLED` | `false` | `false` | `true` or `false`. | Deprecated compatibility fallback only. Prefer request-level `chunking_enabled`; API values take precedence. |
| `INGEST_CHUNKING_STRATEGY` | `page` | `page` | `token`, `page`, or `line`. | Deprecated compatibility fallback only. Prefer request-level `chunking_strategy`; parser capabilities decide which values are valid. Legacy `hybrid` is accepted as an alias for `token`; legacy `line_based` is accepted as an alias for `line`, which Docling rejects in this iteration. |
| `INGEST_CHUNK_MAX_TOKENS` | `768` | `1024` | Integer `>= 32`. | Token budget used by token-based parser chunkers. |
| `INGEST_CHUNK_TOKENIZER_PATH` | unset | `/datastore/models/tokenizers/qwen3-embedding-8b` | Local filesystem path. | Local Hugging Face tokenizer directory for token chunking. Runtime tokenizer downloads are not used by default. |

Removed chunking variables: `INGEST_CHUNK_TOKENIZER_MODEL`,
`INGEST_CHUNK_MERGE_PEERS`, `INGEST_CHUNK_REPEAT_TABLE_HEADER`,
`INGEST_CHUNK_OMIT_HEADER_ON_OVERFLOW`,
`INGEST_CHUNK_OMIT_PREFIX_ON_OVERFLOW`, `INGEST_CHUNK_SIZE_CHARS`, and
`INGEST_CHUNK_OVERLAP_CHARS`. Parser-owned chunkers now own strategy-specific
implementation details.

## RAG Output Compatibility

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_EMBEDDING_OUTPUT_ENABLED` | `true` | `true` | `true` or `false`. | Compatibility setting retained for deployments that already define it. The service now writes the unified RAG ingestion file `rag_chunks.jsonl` instead of a separate `embedding_input.jsonl`. |

## Parsed Document Dispatch And Elastic Handoff

The dispatch queue is mandatory in v1.5. Parser processes enqueue full parsed
document dispatch items with Markdown, metadata, diagnostics, and RAG records.
The dispatcher service stores local artifacts, sends Elastic bulk requests, or
does both according to `INGEST_DISPATCH_SINK_MODE`.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_PARSER_PROCESS_COUNT` | `2` | `2` | Integer `>= 1`. | Number of independent parser processes. Each parser process handles one queued parse workflow at a time when Dramatiq is launched with matching `--processes`. |
| `INGEST_PARSER_THREADS_PER_PROCESS` | `1` | `1` | Integer `>= 1`. | Dramatiq actor threads per parser process. Keep this at `1` for predictable one-document-per-process GPU deployments. |
| `INGEST_PARSER_WORKER_COUNT` | `2` | `2` | Integer `>= 1`. | Deprecated compatibility alias for `INGEST_PARSER_PROCESS_COUNT`. If both are set, `INGEST_PARSER_PROCESS_COUNT` wins. |
| `INGEST_DISPATCH_WORKER_COUNT` | `2` | `2` | Integer `>= 1`. | Dispatch worker thread count. Dispatch concurrency keeps the existing one-process worker model. |
| `INGEST_DRAMATIQ_PARSER_TIME_LIMIT_MS` | `14400000` | `14400000` | Integer `>= 1`. | Dramatiq parser actor time limit in milliseconds. The default is 4 hours so long OCR/PDF jobs are not interrupted by Dramatiq's 10 minute middleware default. |
| `INGEST_DRAMATIQ_DISPATCH_TIME_LIMIT_MS` | `600000` | `600000` | Integer `>= 1`. | Dramatiq dispatch actor time limit in milliseconds. |
| `INGEST_PARSER_MAX_RETRY_ATTEMPTS` | `3` | `3` | Integer `>= 0`. | Retry budget for parser failures. Retried jobs are marked `retrying` and republished at the parser queue tail before final failure. |
| `INGEST_DISPATCH_QUEUE_MAX_SIZE` | `100` | `100` | Integer `>= 1`. | Maximum number of parsed document dispatch items waiting in the process-local dispatch queue. |
| `INGEST_DISPATCH_QUEUE_MAX_PAYLOAD_BYTES` | unset | `104857600` | Unset or integer `>= 1`. | Optional maximum serialized size for one parsed document dispatch payload. Leave unset for no per-item limit; set it to fail oversized documents explicitly instead of allowing unbounded memory growth. |
| `INGEST_DISPATCH_MAX_BULK_SIZE` | `5` | `5` | Integer from `1` to `5`. | Maximum number of parsed documents drained by the dispatcher in one batch. Elastic receives one bulk item per RAG record. |
| `INGEST_DISPATCH_IDLE_INTERVAL_SECONDS` | `0.5` | `0.5` | Float `> 0`. | Dispatcher worker sleep interval while the queue is empty. |
| `INGEST_DISPATCH_SINK_MODE` | `local` | `local_and_elastic` | `local`, `elastic`, or `local_and_elastic`. | Dispatch target mode. |
| `INGEST_DISPATCH_MAX_RETRIES` | `3` | `3` | Integer `>= 0`. | Retry budget for dispatcher sink failures before a job is marked `failed`. |
| `INGEST_EMBEDDING_ELASTIC_URL` | unset | `https://elastic.example:9200` | Unset or Elasticsearch URL string. | Base URL for Elasticsearch. Required when the dispatch sink mode includes Elastic. |
| `INGEST_EMBEDDING_ELASTIC_USERNAME` | unset | `elastic-user` | Unset or any username string. | Optional basic-auth username for the remote endpoint. |
| `INGEST_EMBEDDING_ELASTIC_PASSWORD` | unset | local secret | Unset or any password string. | Optional basic-auth password. This is never included in grouped config metadata; only a boolean `elastic_password_configured` is exposed. |
| `INGEST_EMBEDDING_ELASTIC_INDEX` | `ingest-embedding-input` | `open-rag-embeddings-v2` | Non-empty Elasticsearch index name. | Target Elasticsearch index for RAG records sent through the official bulk helper. |
| `INGEST_EMBEDDING_ELASTIC_MAPPING_VERSION` | `v1` | `v2` | `v1`, `dense_vector`, `dense_vector_v1`, `v2`, `semantic_text`, or `semantic_text_v2`. | Dispatcher output schema. `v1` embeds `content` and `title` through a dense-vector ingest pipeline. `v2` uses the index default pipeline to copy `content` and `title` into `semantic_text` fields for inference and keeps those semantic fields in `_source`. |
| `INGEST_EMBEDDING_ELASTIC_PIPELINE` | unset | `qwen3_embeddings_pipeline` | Unset or any Elasticsearch ingest pipeline name. | Optional Elasticsearch ingest pipeline name for dispatcher bulk actions. Use this for v1 dense-vector embedding fields. Leave blank for v2 because `elastic/open-rag-embeddings-v2.json` sets `index.default_pipeline=open_rag_embeddings_v2_semantic_pipeline`. |
| `INGEST_EMBEDDING_ELASTIC_VERIFY_CERTS` | `true` | `false` | `true` or `false`. | Enables TLS certificate verification. Keep `true` outside local lab environments. |
| `INGEST_EMBEDDING_ELASTIC_REQUEST_TIMEOUT_SECONDS` | `30` | `30` | Float `> 0`. | Timeout for Elasticsearch bulk helper requests. |
| `INGEST_EMBEDDING_ELASTIC_MAX_RETRIES` | `3` | `3` | Integer `>= 0`. | Elasticsearch client retry count for bulk request transport retries. |

## Confidence Metadata

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_CONFIDENCE_OUTPUT_ENABLED` | `true` | `true` | `true` or `false`. | Retained for compatibility. Confidence summaries are now embedded in `document_metadata.json` and RAG record metadata when Docling reports scores. |
| `INGEST_CONFIDENCE_MIN_DOCUMENT_SCORE` | unset | `0.8` | Unset or float from `0` to `1`. | Optional minimum acceptable document score. When set, documents below the threshold create warnings or failures depending on `INGEST_CONFIDENCE_WARN_ONLY`. |
| `INGEST_CONFIDENCE_WARN_ONLY` | `true` | `true` | `true` or `false`. | When `true`, low confidence is reported as warnings. When `false`, low confidence is treated as an ingestion problem. |

## Progress Logging

Progress updates are emitted to stdout as structured `ingestion.progress`
events and persisted into each job row under `metadata.progress` plus a bounded
`metadata.progress_history` list. PDF/image conversions report Docling model
loading, page completion, assembly, enrichment, and normalization stages.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_PROGRESS_LOG_INTERVAL_SECONDS` | `30` | `30` | Float `>= 0`. | Heartbeat interval while Docling is busy but has not completed another page yet, such as during model loading or a long VLM call. Set `0` to disable heartbeat updates. |
| `INGEST_PROGRESS_PAGE_INTERVAL` | `1` | `1` | Integer `>= 1`. | Minimum number of newly completed pages between page progress updates. Keep `1` for maximum visibility; increase for very large documents if SQLite/job metadata writes become too chatty. |
| `INGEST_PROGRESS_HISTORY_LIMIT` | `50` | `50` | Integer `>= 1`. | Maximum number of recent progress events retained in `metadata.progress_history` for each job. The latest event is always available in `metadata.progress`. |
| `INGEST_CORS_ALLOW_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated HTTP(S) origins. | Browser origins allowed to call the API. Add the frontend dev-server origin when testing from another host. |

## Docling Common Options

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_DOCLING_ACCELERATOR_DEVICE` | `auto` | `cuda` | `auto`, `cpu`, `cuda`, `cuda:N`, `mps`, or `xpu`. | Docling accelerator target. Use `cuda` on NVIDIA GPU hosts and `cpu` for predictable CPU-only runs. |
| `INGEST_DOCLING_NUM_THREADS` | `4` | `32` | Integer `>= 1`. | Thread count passed to Docling accelerator options. Higher values can improve throughput on large CPU/GPU hosts but can also increase memory pressure. |
| `INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2` | `false` | `false` | `true` or `false`. | Enables FlashAttention 2 in Docling accelerator options. Keep disabled unless `flash-attn` is installed and verified for the CUDA/PyTorch build. |
| `INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS` | `true` | `true` | `true` or `false`. | Allows Docling external plugins. Required for the `docling-surya` OCR plugin and any custom Docling plugin discovered through the `docling` entry point. |
| `INGEST_DOCLING_PIPELINE` | `standard` | `standard` | `standard`, `vlm`, or `auto`. | Default pipeline. `standard` supports all configured formats. Direct `vlm` mode is currently PDF/image only. `auto` currently resolves to standard behavior. |

Docling engine caching is enabled, engine warmup is disabled, and idle engine
eviction is disabled. Docling input formats are derived from
`INGEST_ALLOWED_UPLOAD_EXTENSIONS`. Queue-level document concurrency follows
`INGEST_PARSER_PROCESS_COUNT`; Docling's own per-document batching and RemoteLLM
request concurrency are configured separately below.

## Standard PDF/Image Pipeline Options

These variables are named `PDF` because Docling exposes this part of the API as
`PdfPipelineOptions`. In this service they are used for PDF and image inputs
when the standard pipeline is selected.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_DOCLING_PDF_OCR_ENGINE` | `suryaocr` | `suryaocr` | Any non-empty Docling OCR engine id. Common values: `auto`, `suryaocr`, `easyocr`, `rapidocr`, `tesseract`, `tesserocr`, `ocrmac`, `kserve_v2_ocr`, or plugin-provided ids. | OCR engine name passed through Docling's OCR factory. |
| `INGEST_DOCLING_PDF_OCR_USE_GPU` | unset | `true` | Unset, `true`, or `false`. | Optional GPU hint for OCR engines with a `use_gpu` option. Leave unset to let Docling or the OCR engine decide. |
| `INGEST_DOCLING_PDF_LAYOUT_MODEL` | `docling-layout-heron-101` | `docling-layout-heron-101` | Any Docling layout model key supported by this service, such as `docling-layout-heron-101` or `docling-layout-v2`. | Layout model preset used by Docling layout analysis. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND` | `tableformer` | `tableformer` | `tableformer`. | Table structure backend. |
| `INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET` | `document_figure_classifier_v2` | `document_figure_classifier_v2` | Docling picture-classifier preset string. | Picture classifier preset. |
| `INGEST_DOCLING_PERF_PAGE_BATCH_SIZE` | `32` | `32` | Integer `>= 1`. | Docling page batch size used by Docling's internal pipeline scheduling. |
| `INGEST_DOCLING_PDF_OCR_BATCH_SIZE` | `32` | `32` | Integer `>= 1`. | OCR stage batch size passed to `ThreadedPdfPipelineOptions`. |
| `INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE` | `32` | `32` | Integer `>= 1`. | Layout stage batch size passed to `ThreadedPdfPipelineOptions`. |
| `INGEST_DOCLING_PDF_TABLE_BATCH_SIZE` | `32` | `32` | Integer `>= 1`. | Table-structure stage batch size passed to `ThreadedPdfPipelineOptions`. |
| `INGEST_DOCLING_PDF_QUEUE_MAX_SIZE` | `512` | `512` | Integer `>= 1`. | Internal PDF pipeline queue size passed to `ThreadedPdfPipelineOptions`. |
| `INGEST_DOCLING_PDF_BATCH_POLLING_INTERVAL_SECONDS` | unset | `0.5` | Unset or float `> 0`. | Optional Docling threaded pipeline polling interval. Leave unset to use Docling's default. |

OCR is always enabled and defaults to English. Request-specific OCR languages
are selected through the ingest API. TableFormer accurate mode with cell
matching and RemoteLLM picture descriptions are enabled by default. Picture
descriptions use `INGEST_DOCLING_VLM_MODEL` and a fixed token budget of `2048`.

## Full VLM Pipeline Options

These settings apply when `pipeline=vlm` is selected for PDF or image inputs.
They do not control standard-pipeline picture descriptions, which use the
same RemoteLLM endpoint and `INGEST_DOCLING_VLM_MODEL`.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_DOCLING_VLM_MODEL` | `Qwen/Qwen3-VL-8B-Instruct` | `Qwen/Qwen3-VL-8B-Instruct` | Any non-empty model id accepted by the RemoteLLM endpoint. | Full-page VLM model identifier. |
| `INGEST_DOCLING_VLM_PROMPT` | `Convert this page to markdown.` | `"Convert this page to markdown."` | Any string. Quote values with spaces when shell-sourcing env files. | Prompt for full-page VLM conversion. |
| `INGEST_DOCLING_VLM_RESPONSE_FORMAT` | `markdown` | `markdown` | `doctags`, `doclang`, `markdown`, `deepseekocr_markdown`, `html`, `otsl`, or `plaintext`. | Expected Docling VLM response format. |
| `INGEST_DOCLING_VLM_SCALE` | `2.0` | `2.0` | Float `> 0`. | Page image scale used before VLM inference. Higher values can improve OCR/detail quality but increase memory and latency. |
| `INGEST_DOCLING_REMOTE_LLM_URL` | `http://localhost:8000/v1/chat/completions` | `http://127.0.0.1:8000/v1/chat/completions` | Non-empty HTTP or HTTPS URL. | OpenAI-compatible chat completions endpoint used for full-page VLM and picture-description requests. |
| `INGEST_DOCLING_REMOTE_LLM_MODEL` | unset | `Qwen/Qwen3-VL-8B-Instruct` | Unset or any model id accepted by the RemoteLLM endpoint. | Optional model id sent in the RemoteLLM request. If unset, full-page VLM uses `INGEST_DOCLING_VLM_MODEL`; picture descriptions use their picture-description model. |
| `INGEST_DOCLING_REMOTE_LLM_API_KEY` | unset | unset | Unset or any API key string. | Optional API key for the RemoteLLM endpoint. Keep this only in local `.env`, never in committed env files. |
| `INGEST_DOCLING_REMOTE_LLM_API_KEY_HEADER` | `Authorization` | `Authorization` | Any HTTP header name string. | Header name used for the optional RemoteLLM API key. |
| `INGEST_DOCLING_REMOTE_LLM_API_KEY_SCHEME` | `Bearer` | `Bearer` | Any string, including empty. | Prefix used before the API key value. Leave empty only if the endpoint expects the raw key. |
| `INGEST_DOCLING_REMOTE_LLM_TIMEOUT_SECONDS` | `90` | `90` | Float `> 0`. | HTTP timeout for RemoteLLM requests from Docling. Increase for very slow pages or large models. |
| `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY` | `2` | `2` | Integer `>= 1`. | RemoteLLM request concurrency for VLM conversion and picture description. This remains remote-only and does not load a local VLM. |
| `INGEST_DOCLING_REMOTE_LLM_PAGE_BATCH_SIZE` | unset | `8` | Unset or integer `>= 1`. | Optional Docling page batch size floor for remote LLM image/page calls. If unset, RemoteLLM concurrency is used. |
| `INGEST_DOCLING_REMOTE_LLM_MAX_TOKENS` | `4096` | `4096` | Integer `>= 1`. | `max_tokens` sent to the RemoteLLM endpoint for full-page VLM conversion. |
| `INGEST_DOCLING_REMOTE_LLM_TEMPERATURE` | `0` | `0` | Float `>= 0`. | Temperature sent to the RemoteLLM endpoint. Keep `0` for deterministic document conversion. |
| `INGEST_DOCLING_REMOTE_LLM_PROVIDER` | `openai_compatible` | `openai_compatible` | `openai_compatible` or alias `openai`. | Remote provider type. Current implementation supports OpenAI-compatible chat completions. |
| `INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_ENABLED` | `false` | `false` | `true` or `false`. | When `true`, API startup checks the RemoteLLM endpoint and fails fast if it is unreachable. |
| `INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_TIMEOUT_SECONDS` | `5` | `5` | Float `> 0`. | Timeout for the startup and `/health/remote-llm` checks. |

RemoteLLM request concurrency is independent from parser process count. Increase
`INGEST_DOCLING_REMOTE_LLM_CONCURRENCY` only when the external inference server
can accept the additional parallel requests.

## XBRL Options

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_DOCLING_XBRL_ENABLE_LOCAL_FETCH` | `false` | `true` | `true` or `false`. | Allows Arelle/Docling XBRL processing to load local taxonomy/resources referenced by the document. The GPU environment enables this for local sample files. |
| `INGEST_DOCLING_XBRL_ENABLE_REMOTE_FETCH` | `false` | `false` | `true` or `false`. | Allows remote taxonomy/resource fetching. Keep disabled for reproducibility and network safety unless the ingestion environment is allowed to fetch taxonomies. |
| `INGEST_DOCLING_XBRL_TAXONOMY_PATH` | unset | `/path/to/xbrl-taxonomy` | Unset or filesystem path. | Optional local taxonomy path to use for XBRL processing. Prefer this over remote fetching for controlled deployments. |

## NVIDIA/GPU Helper Variables

These variables are used by `env-cuda-gpu` but are not part of the Pydantic
`Settings` model. They configure the host/runtime libraries around the service.

| Variable | Example | Allowed Values | Explanation |
| --- | --- | --- | --- |
| `CUDA_VISIBLE_DEVICES` | `0` | CUDA device id list such as `0`, `1`, or `0,1`; unset means all visible devices. | Limits CUDA-visible GPUs for PyTorch/Docling. Use a comma-separated list for multiple GPUs. |
| `NVIDIA_VISIBLE_DEVICES` | `0` | NVIDIA device id list, `all`, `none`, or unset. | Docker/NVIDIA runtime device visibility. Useful when running through NVIDIA container tooling. |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | Comma-separated NVIDIA capabilities such as `compute`, `utility`, `graphics`, `video`, `display`, `compat32`, or `all`. | NVIDIA container runtime capabilities needed for compute workloads and device utilities. |
| `PYTORCH_CUDA_ALLOC_CONF` | `expandable_segments:True` | PyTorch allocator configuration string. | PyTorch allocator tuning that can reduce fragmentation for large OCR/layout/table workloads. |
| `TOKENIZERS_PARALLELISM` | `false` | `true` or `false`. | Disables tokenizer thread-pool warnings and avoids oversubscription in some Hugging Face workloads. |

## Operational Notes

- API query parameters can override selected parse choices for one request:
  `pipeline`, `chunking_enabled`, and `chunking_strategy`.
- Direct `pipeline=vlm` mode is supported only for PDF and image inputs in this
  service version.
- Prefer request-level `chunking_enabled=false` when the downstream embedding
  store owns chunking. `INGEST_CHUNKING_ENABLED` remains only as a deprecated
  fallback for clients that omit chunking options.
- CPU hosts should normally use `INGEST_DOCLING_PDF_OCR_ENGINE=auto` unless the
  selected OCR plugin is installed and compatible with the platform.
