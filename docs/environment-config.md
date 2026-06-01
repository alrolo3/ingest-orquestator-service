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
| `env-cpu` | Source-safe CPU environment for macOS and Linux. It avoids external Docling OCR plugins and disables GPU-heavy enrichments. |
| `env-cuda-gpu` | Source-safe NVIDIA GPU environment tuned for an A100 80GB class machine. It enables CUDA, SuryaOCR, Qwen3 VLM stages through Transformers, higher batch sizes, and larger uploads. |

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

This is the upload gate. Docling format support is controlled separately by
`INGEST_DOCLING_ALLOWED_FORMATS`.

## Chunking

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_CHUNKING_ENABLED` | `true` | `true` | `true` or `false`. | Enables chunk generation during ingestion. Disable when the downstream vector database or RAG pipeline owns chunking. |
| `INGEST_CHUNKING_STRATEGY` | `hybrid` | `hybrid` | `hybrid`, `line_based`, or `legacy_char`. | Chunking strategy. `hybrid` uses Docling `HybridChunker`; `line_based` uses Docling line-based token chunking; `legacy_char` uses the service's character splitter. |
| `INGEST_CHUNK_MAX_TOKENS` | `768` | `1024` | Integer `>= 32`. | Maximum token budget for Docling chunkers. The current service tokenizer is whitespace-based and uses this as its word budget. |
| `INGEST_CHUNK_TOKENIZER_MODEL` | unset | `sentence-transformers/all-MiniLM-L6-v2` | Unset or any tokenizer model identifier string. | Optional tokenizer model identifier reserved for tokenizer-aware chunking metadata. The current implementation records this value but uses the built-in whitespace tokenizer. |
| `INGEST_CHUNK_MERGE_PEERS` | `true` | `true` | `true` or `false`. | Passed to Docling `HybridChunker`. Allows neighboring compatible document items to be merged into larger, more useful RAG chunks. |
| `INGEST_CHUNK_REPEAT_TABLE_HEADER` | `true` | `true` | `true` or `false`. | Passed to Docling `HybridChunker`. Repeats table headers when tables overflow across chunks so table chunks remain understandable alone. |
| `INGEST_CHUNK_OMIT_HEADER_ON_OVERFLOW` | `false` | `false` | `true` or `false`. | Passed to Docling `HybridChunker`. When `true`, omits repeated headers if a chunk overflows the token budget. |
| `INGEST_CHUNK_OMIT_PREFIX_ON_OVERFLOW` | `false` | `false` | `true` or `false`. | Passed to Docling `LineBasedTokenChunker`. When `true`, omits context prefixes when lines overflow the token budget. |
| `INGEST_CHUNK_SIZE_CHARS` | `1200` | `1200` | Integer `>= 100`. | Character chunk size used only by `legacy_char` or by fallback behavior if Docling chunking fails. |
| `INGEST_CHUNK_OVERLAP_CHARS` | `150` | `150` | Integer `>= 0`. | Character overlap used only by `legacy_char` or fallback behavior. |

## RAG Output Compatibility

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_EMBEDDING_OUTPUT_ENABLED` | `true` | `true` | `true` or `false`. | Compatibility setting retained for deployments that already define it. The service now writes the unified RAG ingestion file `rag_chunks.jsonl` instead of a separate `embedding_input.jsonl`. |

## Parsed Document Dispatch And Elastic Handoff

The dispatch queue is mandatory in v1.5. Parser workers enqueue full parsed
document dispatch items with Markdown, metadata, diagnostics, and RAG records.
The dispatcher service stores local artifacts, sends Elastic bulk requests, or
does both according to `INGEST_DISPATCH_SINK_MODE`.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_PARSER_WORKER_COUNT` | `2` | `4` | Integer `>= 1`. | Number of parser worker threads that process queued uploaded files. |
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
| `INGEST_DOCLING_ENGINE_CACHE_ENABLED` | `true` | `true` | `true` or `false`. | Reuses Docling `DocumentConverter` instances across API jobs for the same input format, pipeline, and effective options. Keep enabled on GPU hosts so models stay loaded instead of reloading per document. |
| `INGEST_DOCLING_ENGINE_WARMUP_ENABLED` | `false` | `false` | `true` or `false`. | When enabled, the API initializes configured Docling pipelines at startup. This moves first-request model loading to startup. |
| `INGEST_DOCLING_ENGINE_WARMUP_FORMATS` | `pdf` | `pdf` | Comma-separated subset of supported Docling input formats. | Formats passed to Docling `initialize_pipeline(...)` during warmup. Use only formats you expect to process immediately. |
| `INGEST_DOCLING_GPU_ENGINE_CONCURRENCY` | `1` | `1` | Integer `>= 1`. | Maximum concurrent conversions allowed through one cached Docling engine. Keep `1` for large GPU models unless the pipeline is verified thread-safe under load. |
| `INGEST_DOCLING_GPU_BATCH_MAX_DOCUMENTS` | `5` | `5` | Integer from `1` to `32`. | Maximum same-format documents the scheduler combines before calling Docling `convert_all(...)`. This is independent from the Elastic bulk size. |
| `INGEST_DOCLING_GPU_BATCH_WAIT_MS` | `250` | `250` | Integer `>= 0`. | Milliseconds to wait for compatible documents before flushing a conversion batch. Use `0` to disable cross-worker Docling batching. |
| `INGEST_DOCLING_ENGINE_IDLE_TTL_SECONDS` | `0` | `0` | Integer `>= 0`. | Idle time before cached engines are evicted. `0` means never evict, which is the preferred GPU setting when model reload cost is high. |
| `INGEST_DOCLING_PERF_PAGE_BATCH_SIZE` | unset | `32` | Unset or integer `>= 1`. | Optional global Docling `settings.perf.page_batch_size`. For RemoteLLM, keep it greater than or equal to `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY`. |
| `INGEST_DOCLING_ALLOWED_FORMATS` | Multi-format list | `pdf,image,docx` | Comma-separated subset of `pdf`, `image`, `docx`, `pptx`, `html`, `md`, `xlsx`, `csv`, `json_docling`, `asciidoc`, `latex`, `vtt`, `xml_jats`, `xml_uspto`, `xml_xbrl`, `mets_gbs`, or `audio`. | Docling `InputFormat` names allowed by `DocumentConverter`. |
| `INGEST_DOCLING_PIPELINE` | `standard` | `standard` | `standard`, `vlm`, or `auto`. | Default pipeline. `standard` supports all configured formats. Direct `vlm` mode is currently PDF/image only. `auto` currently resolves to standard behavior. |

## Standard PDF/Image Pipeline Options

These variables are named `PDF` because Docling exposes this part of the API as
`PdfPipelineOptions`. In this service they are used for PDF and image inputs
when the standard pipeline is selected.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_DOCLING_PDF_DO_OCR` | `true` | `true` | `true` or `false`. | Enables OCR in the standard PDF/image pipeline. |
| `INGEST_DOCLING_PDF_OCR_ENGINE` | `suryaocr` | `suryaocr` | Any non-empty Docling OCR engine id. Common values: `auto`, `suryaocr`, `easyocr`, `rapidocr`, `tesseract`, `tesserocr`, `ocrmac`, `kserve_v2_ocr`, or plugin-provided ids. | OCR engine name passed through Docling's OCR factory. |
| `INGEST_DOCLING_PDF_OCR_LANGUAGES` | `en` | `en,es` | Comma-separated OCR language codes such as `en`, `es`, or `fr`. | OCR language codes assigned to the selected OCR options when supported by the engine. |
| `INGEST_DOCLING_PDF_OCR_USE_GPU` | unset | `true` | Unset, `true`, or `false`. | Optional GPU hint for OCR engines with a `use_gpu` option. Leave unset to let Docling or the OCR engine decide. |
| `INGEST_DOCLING_PDF_DO_TABLE_STRUCTURE` | `true` | `true` | `true` or `false`. | Enables table structure extraction in the standard pipeline. |
| `INGEST_DOCLING_PDF_LAYOUT_MODEL` | `docling-layout-heron-101` | `docling-layout-heron-101` | `docling-layout-heron`, `docling-layout-heron-101`, `docling-layout-egret-medium`, `docling-layout-egret-large`, `docling-layout-egret-xlarge`, `docling-layout-v2`, or underscore aliases for those names. | Layout model preset used by Docling layout analysis. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND` | `tableformer` | `tableformer` | `tableformer` or `granite_vision`. | Table structure backend. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_MODE` | `accurate` | `accurate` | `fast` or `accurate`. | TableFormer mode. Accurate mode favors quality over speed. |
| `INGEST_DOCLING_PDF_TABLE_DO_CELL_MATCHING` | `true` | `true` | `true` or `false`. | Enables cell matching for TableFormer output so detected table cells align with document content. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_VLM_MODEL` | `granite-vision-4.1-4b` | `granite-vision-4.1-4b` | `granite-vision-4.1-4b` or `ibm-granite/granite-vision-4.1-4b`. | Model identifier used when the table backend is `granite_vision`. It is not used by the default `tableformer` backend. |
| `INGEST_DOCLING_PDF_DO_PICTURE_CLASSIFICATION` | `true` | `true` | `true` or `false`. | Enables picture classification for detected figures. Disable for faster parses when figure types are not needed. |
| `INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET` | `document_figure_classifier_v2` | `document_figure_classifier_v2` | Docling picture-classifier preset string. This project is tested with `document_figure_classifier_v2`. | Picture classifier preset. The project maps this to Docling `DocumentFigureClassifier-v2.5`. |
| `INGEST_DOCLING_PDF_DO_PICTURE_DESCRIPTION` | `true` | `true` | `true` or `false`. | Enables VLM-based descriptions for detected pictures in the standard pipeline. This is separate from full-page `vlm` pipeline mode. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL` | `Qwen/Qwen3-VL-8B-Instruct` | `Qwen/Qwen3-VL-8B-Instruct` | Any non-empty Hugging Face repo id, local model path, or supported service alias such as `granite_vision`. | VLM model used for picture descriptions in the standard pipeline. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_RUNTIME` | `transformers` | `remote_llm` | `auto`, `auto_inline`, `transformers`, `remote_llm`, or aliases `remote`, `api`. | Runtime requested for standard-pipeline picture descriptions. Use `remote_llm` for external OpenAI-compatible inference services. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_PROMPT` | `Describe this image.` | `"Describe this image."` | Any string. Quote values with spaces when shell-sourcing env files. | Prompt sent to the picture-description model. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MAX_NEW_TOKENS` | `1024` | `1024` | Integer `>= 1`. | Maximum tokens generated by the standard-pipeline picture-description model. The default is higher than Docling's engine default to avoid Qwen3 descriptions ending mid-sentence. |
| `INGEST_DOCLING_PDF_DO_CODE_ENRICHMENT` | `true` | `true` | `true` or `false`. | Enables code enrichment in the standard pipeline when Docling supports it for the input. |
| `INGEST_DOCLING_PDF_DO_FORMULA_ENRICHMENT` | `true` | `true` | `true` or `false`. | Enables formula enrichment in the standard pipeline when Docling supports it for the input. |
| `INGEST_DOCLING_PDF_CODE_FORMULA_PRESET` | `codeformulav2` | `codeformulav2` | Docling code/formula preset string. This project is tested with `codeformulav2`. | Code/formula model preset. The project maps this to Docling `CodeFormulaV2`. |
| `INGEST_DOCLING_PDF_OCR_BATCH_SIZE` | `4` | `32` | Integer `>= 1`. | OCR batch size for the standard PDF/image pipeline. Increase on large GPUs; reduce on CPU or if memory is tight. |
| `INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE` | `4` | `32` | Integer `>= 1`. | Layout model batch size. Increase for throughput when GPU memory allows. |
| `INGEST_DOCLING_PDF_TABLE_BATCH_SIZE` | `4` | `32` | Integer `>= 1`. | Table structure batch size. Increase for throughput when GPU memory allows. |
| `INGEST_DOCLING_PDF_QUEUE_MAX_SIZE` | `100` | `512` | Integer `>= 1`. | Internal Docling queue size. Larger values can improve pipeline throughput but consume more memory. |

## Full VLM Pipeline Options

These settings apply when `pipeline=vlm` is selected for PDF or image inputs.
They do not control standard-pipeline picture descriptions, which use the
`INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_*` settings above.

| Variable | Code Default | Example | Allowed Values | Explanation |
| --- | --- | --- | --- | --- |
| `INGEST_DOCLING_VLM_MODEL` | `Qwen/Qwen3-VL-8B-Instruct` | `Qwen/Qwen3-VL-8B-Instruct` | Any non-empty Hugging Face repo id, local model path, or supported service alias such as `granite_vision`. | Full-page VLM model repository or identifier. |
| `INGEST_DOCLING_VLM_PROMPT` | `Convert this page to markdown.` | `"Convert this page to markdown."` | Any string. Quote values with spaces when shell-sourcing env files. | Prompt for full-page VLM conversion. |
| `INGEST_DOCLING_VLM_RESPONSE_FORMAT` | `markdown` | `markdown` | `doctags`, `doclang`, `markdown`, `deepseekocr_markdown`, `html`, `otsl`, or `plaintext`. | Expected Docling VLM response format. |
| `INGEST_DOCLING_VLM_RUNTIME` | `transformers` | `remote_llm` | `auto`, `auto_inline`, `transformers`, `remote_llm`, or aliases `remote`, `api`. | Runtime requested for full-page VLM conversion. Use `remote_llm` for external OpenAI-compatible inference services. |
| `INGEST_DOCLING_VLM_SCALE` | `2.0` | `2.0` | Float `> 0`. | Page image scale used before VLM inference. Higher values can improve OCR/detail quality but increase memory and latency. |
| `INGEST_DOCLING_VLM_TORCH_DTYPE` | `bfloat16` | `bfloat16` | Unset or torch dtype string such as `auto`, `float16`, `bfloat16`, or `float32`. | Torch dtype passed to the VLM loader when supported. A100-class GPUs usually work well with `bfloat16`. |
| `INGEST_DOCLING_VLM_LOAD_IN_8BIT` | `false` | `false` | `true` or `false`. | Requests 8-bit model loading where supported. This can reduce memory use but may require extra dependencies and quality checks. |
| `INGEST_DOCLING_VLM_MAX_NEW_TOKENS` | `4096` | `4096` | Integer `>= 1`. | Maximum tokens generated by the full-page VLM path. Increase for long pages only after checking memory and output truncation behavior. |
| `INGEST_DOCLING_VLM_TRUST_REMOTE_CODE` | `false` | `true` | `true` or `false`. | Allows custom Hugging Face model code for local Transformers VLM loaders. Enable only after inspecting and trusting the model repository. |
| `INGEST_DOCLING_REMOTE_LLM_URL` | `http://localhost:8000/v1/chat/completions` | `http://127.0.0.1:8000/v1/chat/completions` | Non-empty HTTP or HTTPS URL. | OpenAI-compatible chat completions endpoint used when either VLM runtime is `remote_llm`. |
| `INGEST_DOCLING_REMOTE_LLM_MODEL` | unset | `Qwen/Qwen3-VL-8B-Instruct` | Unset or any model id accepted by the RemoteLLM endpoint. | Optional model id sent in the RemoteLLM request. If unset, full-page VLM uses `INGEST_DOCLING_VLM_MODEL`; picture descriptions use their picture-description model. |
| `INGEST_DOCLING_REMOTE_LLM_API_KEY` | unset | unset | Unset or any API key string. | Optional API key for the RemoteLLM endpoint. Keep this only in local `.env`, never in committed env files. |
| `INGEST_DOCLING_REMOTE_LLM_API_KEY_HEADER` | `Authorization` | `Authorization` | Any HTTP header name string. | Header name used for the optional RemoteLLM API key. |
| `INGEST_DOCLING_REMOTE_LLM_API_KEY_SCHEME` | `Bearer` | `Bearer` | Any string, including empty. | Prefix used before the API key value. Leave empty only if the endpoint expects the raw key. |
| `INGEST_DOCLING_REMOTE_LLM_TIMEOUT_SECONDS` | `90` | `90` | Float `> 0`. | HTTP timeout for RemoteLLM requests from Docling. Increase for very slow pages or large models. |
| `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY` | `1` | `8` | Integer `>= 1`. | RemoteLLM request concurrency passed to Docling. Tune this with the inference server's batch capacity. |
| `INGEST_DOCLING_REMOTE_LLM_PAGE_BATCH_SIZE` | unset | `8` | Unset or integer `>= 1`. | Docling page batch size used with RemoteLLM. Keep it greater than or equal to RemoteLLM concurrency. |
| `INGEST_DOCLING_REMOTE_LLM_MAX_TOKENS` | `4096` | `4096` | Integer `>= 1`. | `max_tokens` sent to the RemoteLLM endpoint for full-page VLM conversion. |
| `INGEST_DOCLING_REMOTE_LLM_TEMPERATURE` | `0` | `0` | Float `>= 0`. | Temperature sent to the RemoteLLM endpoint. Keep `0` for deterministic document conversion. |
| `INGEST_DOCLING_REMOTE_LLM_PROVIDER` | `openai_compatible` | `openai_compatible` | `openai_compatible` or alias `openai`. | Remote provider type. Current implementation supports OpenAI-compatible chat completions. |
| `INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_ENABLED` | `false` | `false` | `true` or `false`. | When `true`, API startup checks the RemoteLLM endpoint and fails fast if it is unreachable. |
| `INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_TIMEOUT_SECONDS` | `5` | `5` | Float `> 0`. | Timeout for the startup and `/health/remote-llm` checks. |

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
| `PYTORCH_CUDA_ALLOC_CONF` | `expandable_segments:True` | PyTorch allocator configuration string. | PyTorch allocator tuning that can reduce fragmentation for large VLM/OCR workloads. |
| `TOKENIZERS_PARALLELISM` | `false` | `true` or `false`. | Disables tokenizer thread-pool warnings and avoids oversubscription in some Hugging Face workloads. |

## Operational Notes

- API query parameters can override selected runtime choices for one request:
  `pipeline`, `chunking_enabled`, and `chunking_strategy`.
- Direct `pipeline=vlm` mode is supported only for PDF and image inputs in this
  service version.
- Set `INGEST_CHUNKING_ENABLED=false` or pass `chunking_enabled=false` when the
  downstream embedding store owns chunking.
- CPU hosts should normally use `INGEST_DOCLING_PDF_OCR_ENGINE=auto` unless the
  selected OCR plugin is installed and compatible with the platform.
