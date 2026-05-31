# Docling Ingestion

The service uses Docling's `DocumentConverter` as the integration boundary.
Implementation should follow the official API reference:

- https://docling-project.github.io/docling/reference/document_converter/

## Supported Formats

`INGEST_DOCLING_ALLOWED_FORMATS` controls the Docling `InputFormat` values that
the service allows. The default configuration enables:

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

Full-page VLM conversion is configured separately from picture description:

```text
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_VLM_RESPONSE_FORMAT=markdown
INGEST_DOCLING_VLM_RUNTIME=transformers
```

Picture description still uses the standard PDF pipeline enrichment settings,
for example `INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL`.

## Embedding Output

Every completed parse writes `embedding_input.jsonl` when
`INGEST_EMBEDDING_OUTPUT_ENABLED=true`. Each line contains one embedding record
with the chunk text plus metadata such as source file, parser, pipeline, input
format, page span, and element ids/types.

## Chunking

Chunking is enabled by default because the service produces embedding-ready RAG
artifacts.

```text
INGEST_CHUNKING_ENABLED=true
INGEST_CHUNKING_STRATEGY=hybrid
INGEST_CHUNK_MAX_TOKENS=768
```

Supported strategies:

- `hybrid`: Docling `HybridChunker`. This is the default for RAG ingestion.
- `line_based`: Docling `LineBasedTokenChunker`.
- `legacy_char`: service-local character chunker retained as a fallback.

Set `INGEST_CHUNKING_ENABLED=false` or pass `chunking_enabled=false` when the
embedding database will split the parsed document itself.

## Confidence Scores

When `INGEST_CONFIDENCE_OUTPUT_ENABLED=true`, Docling conversion confidence is
stored in:

- `manifest.json` diagnostics.
- `confidence.json`.
- embedding record metadata summary.

Set `INGEST_CONFIDENCE_MIN_DOCUMENT_SCORE=0.8` to emit a warning when Docling's
mean score is below the threshold. Set `INGEST_CONFIDENCE_WARN_ONLY=false` to
fail ingestion on that validation warning.

## Interface

The supported runtime interface is the FastAPI server. Submit documents with
`POST /v1/ingest/file` and retrieve local artifacts through the job output API.
