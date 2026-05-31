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

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_SERVICE_NAME` | `ingest-orquestator-server` | `ingest-orquestator-server` | Logical service name returned by health/config metadata and useful in logs or deployment labels. |
| `INGEST_STORAGE_DIR` | `.data` | `.data` | Root directory for local runtime state. Uploads, outputs, and SQLite jobs are stored below this path. |
| `INGEST_MAX_UPLOAD_SIZE_MB` | `100` | `2048` | Maximum accepted upload size in MiB for API ingestion. Increase for large PDFs or office documents. |
| `INGEST_ALLOWED_UPLOAD_EXTENSIONS` | Multi-format list | `.pdf,.docx,.md` | Comma-separated file extensions accepted by upload validation and batch directory discovery. Extensions are normalized to lowercase and `.` is added if missing. |
| `INGEST_RETENTION_DAYS` | `30` | `30` | Default retention window for local runtime artifacts when cleanup is run by an operator or maintenance process. |

## Upload Extension Defaults

The checked-in environment files currently include:

```text
.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.md,.markdown,.txt,.html,.htm,.docx,.pptx,.xlsx,.csv,.json,.adoc,.asciidoc,.tex,.latex,.vtt,.jats,.nxml,.uspto,.xbrl
```

This is the upload gate. Docling format support is controlled separately by
`INGEST_DOCLING_ALLOWED_FORMATS`.

## Chunking

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_CHUNKING_ENABLED` | `true` | `true` | Enables chunk generation during ingestion. Disable when the downstream vector database or RAG pipeline owns chunking. |
| `INGEST_CHUNKING_STRATEGY` | `hybrid` | `hybrid` | Chunking strategy. Valid values: `hybrid`, `line_based`, `legacy_char`. `hybrid` uses Docling `HybridChunker`; `line_based` uses Docling line-based token chunking; `legacy_char` uses the service's character splitter. |
| `INGEST_CHUNK_MAX_TOKENS` | `768` | `1024` | Maximum token budget for Docling chunkers. The current service tokenizer is whitespace-based and uses this as its word budget. |
| `INGEST_CHUNK_TOKENIZER_MODEL` | unset | `sentence-transformers/all-MiniLM-L6-v2` | Optional tokenizer model identifier reserved for tokenizer-aware chunking metadata. The current implementation records this value but uses the built-in whitespace tokenizer. |
| `INGEST_CHUNK_MERGE_PEERS` | `true` | `true` | Passed to Docling `HybridChunker`. Allows neighboring compatible document items to be merged into larger, more useful RAG chunks. |
| `INGEST_CHUNK_REPEAT_TABLE_HEADER` | `true` | `true` | Passed to Docling `HybridChunker`. Repeats table headers when tables overflow across chunks so table chunks remain understandable alone. |
| `INGEST_CHUNK_OMIT_HEADER_ON_OVERFLOW` | `false` | `false` | Passed to Docling `HybridChunker`. When `true`, omits repeated headers if a chunk overflows the token budget. |
| `INGEST_CHUNK_OMIT_PREFIX_ON_OVERFLOW` | `false` | `false` | Passed to Docling `LineBasedTokenChunker`. When `true`, omits context prefixes when lines overflow the token budget. |
| `INGEST_CHUNK_SIZE_CHARS` | `1200` | `1200` | Character chunk size used only by `legacy_char` or by fallback behavior if Docling chunking fails. |
| `INGEST_CHUNK_OVERLAP_CHARS` | `150` | `150` | Character overlap used only by `legacy_char` or fallback behavior. |

## Embedding Output

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_EMBEDDING_OUTPUT_ENABLED` | `true` | `true` | Writes `embedding_input.jsonl` from generated chunks. Each record includes chunk text plus document, page, parser, pipeline, element, and provenance metadata for downstream embedding. |

## Embedding Queue And Elastic Handoff

The dispatch queue is mandatory in v1.5. Parser workers enqueue full parsed
documents, and the dispatcher service stores local artifacts, sends Elastic bulk
requests, or does both according to `INGEST_DISPATCH_SINK_MODE`.

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_PARSER_WORKER_COUNT` | `2` | `4` | Number of parser worker threads that process queued uploaded files. |
| `INGEST_DISPATCH_QUEUE_MAX_SIZE` | `100` | `100` | Maximum number of full parsed document results waiting in the process-local dispatch queue. |
| `INGEST_DISPATCH_QUEUE_MAX_PAYLOAD_BYTES` | unset | `104857600` | Optional maximum serialized size for one full parsed document queue payload. Leave unset for no per-item limit; set it to fail oversized documents explicitly instead of allowing unbounded memory growth. |
| `INGEST_DISPATCH_MAX_BULK_SIZE` | `5` | `5` | Maximum number of full documents drained by the dispatcher in one batch. Elastic still receives one bulk item per generated chunk. |
| `INGEST_DISPATCH_IDLE_INTERVAL_SECONDS` | `0.5` | `0.5` | Dispatcher worker sleep interval while the queue is empty. |
| `INGEST_DISPATCH_SINK_MODE` | `local` | `local_and_elastic` | Dispatch target mode. Valid values: `local`, `elastic`, `local_and_elastic`. |
| `INGEST_DISPATCH_MAX_RETRIES` | `3` | `3` | Retry budget for dispatcher sink failures before a job is marked `failed`. |
| `INGEST_DISPATCH_RETRY_BACKOFF_SECONDS` | `1` | `1` | Reserved retry backoff interval for dispatcher retries. |
| `INGEST_EMBEDDING_ELASTIC_URL` | unset | `https://elastic.example:9200` | Base URL for Elasticsearch. Required when the dispatch sink mode includes Elastic. |
| `INGEST_EMBEDDING_ELASTIC_USERNAME` | unset | `elastic-user` | Optional basic-auth username for the remote endpoint. |
| `INGEST_EMBEDDING_ELASTIC_PASSWORD` | unset | local secret | Optional basic-auth password. This is never included in grouped config metadata; only a boolean `elastic_password_configured` is exposed. |
| `INGEST_EMBEDDING_ELASTIC_INDEX` | `ingest-embedding-input` | `open-rag-embeddings-v2` | Target Elasticsearch index for chunk documents sent through the official bulk helper. |
| `INGEST_EMBEDDING_ELASTIC_MAPPING_VERSION` | `v1` | `v2` | Dispatcher output schema. `v1` sends `content` and `title` through a dense-vector ingest pipeline. `v2` sends `content` and `title`; the configured ingest pipeline copies those values into `content_semantic` and `title_semantic` for `semantic_text` inference. Aliases: `dense_vector_v1`, `semantic_text_v2`. |
| `INGEST_EMBEDDING_ELASTIC_PIPELINE` | unset | `open_rag_embeddings_v2_semantic_pipeline` | Optional Elasticsearch ingest pipeline name. Use `qwen3_embeddings_pipeline` for v1 dense-vector embedding fields. Use `open_rag_embeddings_v2_semantic_pipeline` for v2 `semantic_text` fields so Elastic copies `content` to `content_semantic` and `title` to `title_semantic`. |
| `INGEST_EMBEDDING_ELASTIC_VERIFY_CERTS` | `true` | `false` | Enables TLS certificate verification. Keep `true` outside local lab environments. |
| `INGEST_EMBEDDING_ELASTIC_REQUEST_TIMEOUT_SECONDS` | `30` | `30` | Timeout for Elasticsearch bulk helper requests. |
| `INGEST_EMBEDDING_ELASTIC_MAX_RETRIES` | `3` | `3` | Elasticsearch client retry count for bulk request transport retries. |
| `INGEST_EMBEDDING_ELASTIC_INCLUDE_LOCAL_PATHS` | `false` | `false` | Controls whether `metadata.source_path` from embedding records is sent to the remote endpoint. Keep `false` unless the remote embedding system is allowed to receive local filesystem paths. |

## Confidence Output

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_CONFIDENCE_OUTPUT_ENABLED` | `true` | `true` | Writes `confidence.json` and embeds Docling confidence summaries in manifests when Docling reports scores. |
| `INGEST_CONFIDENCE_MIN_DOCUMENT_SCORE` | unset | `0.8` | Optional minimum acceptable document score. When set, documents below the threshold create warnings or failures depending on `INGEST_CONFIDENCE_WARN_ONLY`. |
| `INGEST_CONFIDENCE_WARN_ONLY` | `true` | `true` | When `true`, low confidence is reported as warnings. When `false`, low confidence is treated as an ingestion problem. |

## Docling Common Options

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_DOCLING_ACCELERATOR_DEVICE` | `auto` | `cuda` | Docling accelerator target. Valid values: `auto`, `cpu`, `cuda`, `cuda:N`, `mps`, `xpu`. Use `cuda` on NVIDIA GPU hosts and `cpu` for predictable CPU-only runs. |
| `INGEST_DOCLING_NUM_THREADS` | `4` | `32` | Thread count passed to Docling accelerator options. Higher values can improve throughput on large CPU/GPU hosts but can also increase memory pressure. |
| `INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2` | `false` | `false` | Enables FlashAttention 2 in Docling accelerator options. Keep disabled unless `flash-attn` is installed and verified for the CUDA/PyTorch build. |
| `INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS` | `true` | `true` | Allows Docling external plugins. Required for the `docling-surya` OCR plugin and any custom Docling plugin discovered through the `docling` entry point. |
| `INGEST_DOCLING_ALLOWED_FORMATS` | Multi-format list | `pdf,image,docx` | Comma-separated Docling `InputFormat` names allowed by `DocumentConverter`. Valid values include `pdf`, `image`, `docx`, `pptx`, `html`, `md`, `xlsx`, `csv`, `json_docling`, `asciidoc`, `latex`, `vtt`, `xml_jats`, `xml_uspto`, `xml_xbrl`, `mets_gbs`, and `audio`. |
| `INGEST_DOCLING_PIPELINE` | `standard` | `standard` | Default pipeline. Valid values: `standard`, `vlm`, `auto`. `standard` supports all configured formats. Direct `vlm` mode is currently PDF/image only. `auto` currently resolves to standard behavior. |

## Standard PDF/Image Pipeline Options

These variables are named `PDF` because Docling exposes this part of the API as
`PdfPipelineOptions`. In this service they are used for PDF and image inputs
when the standard pipeline is selected.

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_DOCLING_PDF_DO_OCR` | `true` | `true` | Enables OCR in the standard PDF/image pipeline. |
| `INGEST_DOCLING_PDF_OCR_ENGINE` | `suryaocr` | `suryaocr` | OCR engine name passed through Docling's OCR factory. Common values include `auto`, `suryaocr`, `easyocr`, `rapidocr`, `tesseract`, and engines from installed plugins. |
| `INGEST_DOCLING_PDF_OCR_LANGUAGES` | `en` | `en,es` | Comma-separated OCR language codes assigned to the selected OCR options when supported by the engine. |
| `INGEST_DOCLING_PDF_OCR_USE_GPU` | unset | `true` | Optional GPU hint for OCR engines with a `use_gpu` option. Leave unset to let Docling or the OCR engine decide. |
| `INGEST_DOCLING_PDF_DO_TABLE_STRUCTURE` | `true` | `true` | Enables table structure extraction in the standard pipeline. |
| `INGEST_DOCLING_PDF_LAYOUT_MODEL` | `docling-layout-heron-101` | `docling-layout-heron-101` | Layout model preset used by Docling layout analysis. The configured default is Docling Heron layout. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND` | `tableformer` | `tableformer` | Table structure backend. Valid values: `tableformer` or `granite_vision`. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_MODE` | `accurate` | `accurate` | TableFormer mode. Valid values: `fast` or `accurate`. Accurate mode favors quality over speed. |
| `INGEST_DOCLING_PDF_TABLE_DO_CELL_MATCHING` | `true` | `true` | Enables cell matching for TableFormer output so detected table cells align with document content. |
| `INGEST_DOCLING_PDF_TABLE_STRUCTURE_VLM_MODEL` | `granite-vision-4.1-4b` | `granite-vision-4.1-4b` | Model identifier used when the table backend is `granite_vision`. It is not used by the default `tableformer` backend. |
| `INGEST_DOCLING_PDF_DO_PICTURE_CLASSIFICATION` | `true` | `true` | Enables picture classification for detected figures. Disable for faster parses when figure types are not needed. |
| `INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET` | `document_figure_classifier_v2` | `document_figure_classifier_v2` | Picture classifier preset. The project maps this to Docling `DocumentFigureClassifier-v2.5`. |
| `INGEST_DOCLING_PDF_DO_PICTURE_DESCRIPTION` | `true` | `true` | Enables VLM-based descriptions for detected pictures in the standard pipeline. This is separate from full-page `vlm` pipeline mode. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL` | `Qwen/Qwen3-VL-8B-Instruct` | `Qwen/Qwen3-VL-8B-Instruct` | VLM model used for picture descriptions in the standard pipeline. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_RUNTIME` | `transformers` | `vllm` | Runtime requested for standard-pipeline picture descriptions. Valid values: `auto`, `auto_inline`, `transformers`, `vllm`. vLLM is used only for supported presets unless unverified models are explicitly allowed. |
| `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_PROMPT` | `Describe this image.` | `"Describe this image."` | Prompt sent to the picture-description model. Quote this value in shell-sourced env files because it contains spaces. |
| `INGEST_DOCLING_PDF_DO_CODE_ENRICHMENT` | `true` | `true` | Enables code enrichment in the standard pipeline when Docling supports it for the input. |
| `INGEST_DOCLING_PDF_DO_FORMULA_ENRICHMENT` | `true` | `true` | Enables formula enrichment in the standard pipeline when Docling supports it for the input. |
| `INGEST_DOCLING_PDF_CODE_FORMULA_PRESET` | `codeformulav2` | `codeformulav2` | Code/formula model preset. The project maps this to Docling `CodeFormulaV2`. |
| `INGEST_DOCLING_PDF_OCR_BATCH_SIZE` | `4` | `32` | OCR batch size for the standard PDF/image pipeline. Increase on large GPUs; reduce on CPU or if memory is tight. |
| `INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE` | `4` | `32` | Layout model batch size. Increase for throughput when GPU memory allows. |
| `INGEST_DOCLING_PDF_TABLE_BATCH_SIZE` | `4` | `32` | Table structure batch size. Increase for throughput when GPU memory allows. |
| `INGEST_DOCLING_PDF_QUEUE_MAX_SIZE` | `100` | `512` | Internal Docling queue size. Larger values can improve pipeline throughput but consume more memory. |

## Full VLM Pipeline Options

These settings apply when `pipeline=vlm` is selected for PDF or image inputs.
They do not control standard-pipeline picture descriptions, which use the
`INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_*` settings above.

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_DOCLING_VLM_MODEL` | `Qwen/Qwen3-VL-8B-Instruct` | `Qwen/Qwen3-VL-8B-Instruct` | Full-page VLM model repository or identifier. |
| `INGEST_DOCLING_VLM_PROMPT` | `Convert this page to markdown.` | `"Convert this page to markdown."` | Prompt for full-page VLM conversion. Quote in shell-sourced env files because it contains spaces. |
| `INGEST_DOCLING_VLM_RESPONSE_FORMAT` | `markdown` | `markdown` | Expected Docling VLM response format. Valid values: `doctags`, `doclang`, `markdown`, `deepseekocr_markdown`, `html`, `otsl`, `plaintext`. |
| `INGEST_DOCLING_VLM_RUNTIME` | `transformers` | `vllm` | Runtime requested for full-page VLM conversion. Valid values: `auto`, `auto_inline`, `transformers`, `vllm`. vLLM is used only for supported presets unless unverified models are explicitly allowed. |
| `INGEST_DOCLING_VLM_SCALE` | `2.0` | `2.0` | Page image scale used before VLM inference. Higher values can improve OCR/detail quality but increase memory and latency. |
| `INGEST_DOCLING_VLM_TORCH_DTYPE` | `bfloat16` | `bfloat16` | Torch dtype passed to the VLM loader when supported. A100-class GPUs usually work well with `bfloat16`. |
| `INGEST_DOCLING_VLM_LOAD_IN_8BIT` | `false` | `false` | Requests 8-bit model loading where supported. This can reduce memory use but may require extra dependencies and quality checks. |
| `INGEST_DOCLING_VLM_MAX_NEW_TOKENS` | `4096` | `4096` | Maximum tokens generated by the full-page VLM path. Increase for long pages only after checking memory and output truncation behavior. |
| `INGEST_DOCLING_VLM_TRUST_REMOTE_CODE` | unset | `true` | Allows custom Hugging Face model code for VLM loaders. Enable only after inspecting and trusting the model repository. Overrides the legacy vLLM-specific setting when set. |
| `INGEST_DOCLING_VLLM_TENSOR_PARALLEL_SIZE` | `1` | `1` | Tensor parallel size passed to Docling vLLM engine options. Increase only when using multiple GPUs and the model supports tensor parallelism. |
| `INGEST_DOCLING_VLLM_GPU_MEMORY_UTILIZATION` | `0.9` | `0.9` | Fraction of GPU memory vLLM may use. Lower this if the GPU also runs OCR, other models, or concurrent services. |
| `INGEST_DOCLING_VLLM_TRUST_REMOTE_CODE` | `false` | `false` | Backward-compatible alias for remote-code trust. Prefer `INGEST_DOCLING_VLM_TRUST_REMOTE_CODE` for new configuration. |
| `INGEST_DOCLING_VLLM_CUDAGRAPH_MODE` | `PIECEWISE` | `PIECEWISE` | CUDA graph mode passed to Docling vLLM options. Valid values: `NONE`, `FULL`, `PIECEWISE`, `FULL_AND_PIECEWISE`, `FULL_DECODE_ONLY`. |
| `INGEST_DOCLING_VLLM_MODEL_IMPL` | `auto` | `auto` | vLLM model implementation selector. Keep `auto` unless a model requires a specific vLLM implementation. |
| `INGEST_DOCLING_VLLM_ENFORCE_EAGER` | unset | `true` | Optional vLLM eager-mode override used by Docling's custom inline vLLM path. Useful when CUDA graph capture consumes too much memory. |
| `INGEST_DOCLING_VLLM_MAX_MODEL_LEN` | unset | `32768` | Optional vLLM maximum model length for custom inline models. Use this to reduce KV-cache reservation for very long-context models such as Qwen3-VL. |
| `INGEST_DOCLING_VLLM_MAX_NUM_BATCHED_TOKENS` | unset | `8192` | Optional vLLM prefill batching limit for custom inline models. Lower values can reduce memory pressure during smoke tests. |
| `INGEST_DOCLING_VLLM_FALLBACK_RUNTIME` | `transformers` | `transformers` | Runtime used when `vllm` is requested for a model Docling does not document as vLLM-capable. Valid values: `transformers`, `auto_inline`. |
| `INGEST_DOCLING_VLLM_FALLBACK_ON_UNSUPPORTED` | `true` | `true` | When `true`, unsupported vLLM requests fall back. When `false`, unsupported model/runtime pairs fail before model load. |
| `INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS` | `false` | `false` | Allows custom repository ids to be attempted through Docling's inline vLLM path. Treat this as experimental and verify with GPU smoke tests. |

## XBRL Options

| Variable | Code Default | Example | Explanation |
| --- | --- | --- | --- |
| `INGEST_DOCLING_XBRL_ENABLE_LOCAL_FETCH` | `false` | `true` | Allows Arelle/Docling XBRL processing to load local taxonomy/resources referenced by the document. The GPU environment enables this for local sample files. |
| `INGEST_DOCLING_XBRL_ENABLE_REMOTE_FETCH` | `false` | `false` | Allows remote taxonomy/resource fetching. Keep disabled for reproducibility and network safety unless the ingestion environment is allowed to fetch taxonomies. |
| `INGEST_DOCLING_XBRL_TAXONOMY_PATH` | unset | `/path/to/xbrl-taxonomy` | Optional local taxonomy path to use for XBRL processing. Prefer this over remote fetching for controlled deployments. |

## NVIDIA/GPU Helper Variables

These variables are used by `env-cuda-gpu` but are not part of the Pydantic
`Settings` model. They configure the host/runtime libraries around the service.

| Variable | Example | Explanation |
| --- | --- | --- |
| `CUDA_VISIBLE_DEVICES` | `0` | Limits CUDA-visible GPUs for PyTorch/Docling. Use a comma-separated list for multiple GPUs. |
| `NVIDIA_VISIBLE_DEVICES` | `0` | Docker/NVIDIA runtime device visibility. Useful when running through NVIDIA container tooling. |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | NVIDIA container runtime capabilities needed for compute workloads and device utilities. |
| `PYTORCH_CUDA_ALLOC_CONF` | `expandable_segments:True` | PyTorch allocator tuning that can reduce fragmentation for large VLM/OCR workloads. |
| `TOKENIZERS_PARALLELISM` | `false` | Disables tokenizer thread-pool warnings and avoids oversubscription in some Hugging Face workloads. |

## Operational Notes

- API query parameters can override selected runtime choices for one request:
  `pipeline`, `chunking_enabled`, and `chunking_strategy`.
- Direct `pipeline=vlm` mode is supported only for PDF and image inputs in this
  service version.
- Set `INGEST_CHUNKING_ENABLED=false` or pass `chunking_enabled=false` when the
  downstream embedding store owns chunking.
- CPU hosts should normally use `INGEST_DOCLING_PDF_OCR_ENGINE=auto` unless the
  selected OCR plugin is installed and compatible with the platform.
