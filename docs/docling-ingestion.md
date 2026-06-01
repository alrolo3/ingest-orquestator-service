# Docling Ingestion

The service uses Docling's `DocumentConverter` as the integration boundary.
Implementation should follow the official API reference:

- https://docling-project.github.io/docling/reference/document_converter/

## Supported Formats

Docling `InputFormat` values are derived from
`INGEST_ALLOWED_UPLOAD_EXTENSIONS`; there is no separate Docling allow-list.
The default upload extension list enables:

```text
pdf,image,docx,pptx,html,md,xlsx,csv,json_docling,asciidoc,latex,vtt,xml_jats,xml_uspto,xml_xbrl
```

Audio is not enabled by default because it can require additional ASR runtime
dependencies.

XBRL is enabled by default and the project installs `docling[xbrl]`, which pulls
Docling's required `arelle-release` dependency. Docling's XBRL backend also
requires taxonomy fetching to be explicitly enabled:

```text
INGEST_DOCLING_XBRL_ENABLE_LOCAL_FETCH=true
INGEST_DOCLING_XBRL_ENABLE_REMOTE_FETCH=false
# INGEST_DOCLING_XBRL_TAXONOMY_PATH=/path/to/xbrl-taxonomy
```

Keep remote fetch disabled unless you intentionally want XBRL reports to resolve
taxonomy resources from the network.

## Pipeline Matrix

| Input format | `standard` | `vlm` |
| --- | --- | --- |
| PDF | yes | yes |
| Image | yes | yes |
| DOCX, PPTX, HTML, MD, XLSX, CSV | yes | no |
| JSON Docling, AsciiDoc, LaTeX, VTT, XML formats | yes | no |

`pipeline=auto` resolves to `standard`. Pre-rendering Office or HTML
documents to force VLM mode is deferred to a later milestone.

The converter factory builds Docling `FormatOption` objects per format. PDF and
image use `PdfFormatOption`/`ImageFormatOption` with `StandardPdfPipeline` or
`VlmPipeline`; Office, HTML, Markdown, CSV, spreadsheet, and XML routes use the
format option classes exposed by Docling's `DocumentConverter` API. Route
metadata is written to job diagnostics and normalized output.

## Options

The service is RAG-first. Standard parsing writes normalized artifacts,
Docling chunks, embedding JSONL, and confidence output unless those options are
explicitly disabled by environment or API query parameter.

The manifest records a compact `docling_options` object with common settings,
the active format/pipeline options, and configured PDF, VLM, chunking, and
confidence settings. PDF/image options remain in the PDF section because Docling
uses `PdfPipelineOptions` for both standard PDF and image conversion. XBRL
backend options are exposed separately because Docling requires explicit
taxonomy-fetch controls.

## VLM Mode

Full-page VLM conversion is configured separately from picture description, but
both paths use the configured RemoteLLM endpoint. The backend does not load VLM
models in-process.

```text
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_VLM_RESPONSE_FORMAT=markdown
INGEST_DOCLING_REMOTE_LLM_URL=http://localhost:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

Run Qwen3 or equivalent VLM models in a separate OpenAI-compatible inference
endpoint. See [Docling RemoteLLM playbook](docling-remote-llm.md).

Picture descriptions use the same VLM model/runtime configuration and send
requests through the same RemoteLLM endpoint.

## RAG Output

Every completed local dispatch writes `rag_chunks.jsonl`. When chunking is
enabled, each line contains one chunk-level RAG ingestion record. When chunking
is disabled, the file contains one document-level record with the full Markdown
content. This file is the source of truth for Elastic indexing and downstream
RAG/wiki ingestion.

## Chunking

Chunking is selected per ingestion request. The capability response advertises
which strategies are valid for each parser.

```text
INGEST_CHUNKING_ENABLED=false
INGEST_CHUNKING_STRATEGY=page
INGEST_CHUNK_MAX_TOKENS=768
INGEST_CHUNK_TOKENIZER_PATH=/datastore/tokenizers/qwen3-embedding-8b
```

Docling strategies in this version:

- `token`: Docling `HybridChunker` with a local Hugging Face tokenizer loaded
  from `INGEST_CHUNK_TOKENIZER_PATH`.
- `page`: Docling `HierarchicalChunker`.
- `line`: not implemented for Docling and rejected before the job is queued.

Pass `chunking_enabled=true&chunking_strategy=token` or
`chunking_enabled=true&chunking_strategy=page` to enable Docling chunking for a
request. Omit chunking or pass `chunking_enabled=false` when the embedding
database will split the parsed document itself.

## Confidence Scores

Docling conversion confidence is stored in `document_metadata.json` and in each
RAG record's metadata when Docling reports scores.

Set `INGEST_CONFIDENCE_MIN_DOCUMENT_SCORE=0.8` to emit a warning when Docling's
mean score is below the threshold. Set `INGEST_CONFIDENCE_WARN_ONLY=false` to
fail ingestion on that validation warning.

## Interface

The supported runtime interface is the FastAPI server. Submit documents with
`POST /v1/ingest/file` and retrieve local artifacts through the job output API.
