# Docling Ingestion

The service uses Docling's `DocumentConverter` as the integration boundary.
Implementation should follow the official API reference:

- https://docling-project.github.io/docling/reference/document_converter/

## Supported Formats

`INGEST_DOCLING_ALLOWED_FORMATS` controls the Docling `InputFormat` values that
the service allows. The default profile enables:

```text
pdf,image,docx,pptx,html,md,xlsx,csv,json_docling,asciidoc,latex,vtt,xml_jats,xml_uspto,xml_xbrl
```

Audio is not enabled by default because it can require additional ASR runtime
dependencies.

XBRL is enabled by default and the project installs `docling[xbrl]`, which pulls
Docling's required `arelle-release` dependency.

## Pipeline Matrix

| Input format | `standard` | `vlm` |
| --- | --- | --- |
| PDF | yes | yes |
| Image | yes | yes |
| DOCX, PPTX, HTML, MD, XLSX, CSV | yes | no |
| JSON Docling, AsciiDoc, LaTeX, VTT, XML formats | yes | no |

`pipeline=auto` resolves to `standard`. Pre-rendering Office or HTML
documents to force VLM mode is deferred to a later milestone.

## Profiles And Options

`INGEST_PROFILE` selects a preset before Docling options are built:

- `rag_ready`: default. Standard parsing, Docling chunking, embedding JSONL, and
  confidence output.
- `parse_only`: normalized parse artifacts only. Chunking, embedding JSONL, and
  confidence output are disabled.
- `ocr_only`: standard pipeline with OCR enabled and expensive enrichment stages
  disabled.
- `standard_enriched`: standard pipeline with OCR, tables, picture
  classification, picture descriptions, and code/formula enrichment enabled.
- `vlm`: full-page VLM pipeline. Use only with PDF or image inputs.

The manifest records a compact `docling_options` object with common settings,
the active format/pipeline options, and configured PDF, VLM, chunking, and
confidence settings. PDF-only options remain in the PDF section because Docling
exposes them through `PdfFormatOption` and `PdfPipelineOptions`; other formats
use Docling defaults unless their format option is explicitly configured.

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

Chunking is enabled by default because the default `rag_ready` profile is meant
to produce embedding-ready artifacts.

```text
INGEST_CHUNKING_ENABLED=true
INGEST_CHUNKING_STRATEGY=hybrid
INGEST_CHUNK_MAX_TOKENS=768
```

Supported strategies:

- `hybrid`: Docling `HybridChunker`. This is the default for RAG ingestion.
- `line_based`: Docling `LineBasedTokenChunker`.
- `legacy_char`: service-local character chunker retained as a fallback.

Set `INGEST_CHUNKING_ENABLED=false`, use `profile=parse_only`, or pass
`chunking_enabled=false` when the embedding database will split the parsed
document itself.

## Confidence Scores

When `INGEST_CONFIDENCE_OUTPUT_ENABLED=true`, Docling conversion confidence is
stored in:

- `manifest.json` diagnostics.
- `confidence.json`.
- embedding record metadata summary.

Set `INGEST_CONFIDENCE_MIN_DOCUMENT_SCORE=0.8` to emit a warning when Docling's
mean score is below the threshold. Set `INGEST_CONFIDENCE_WARN_ONLY=false` to
fail ingestion on that validation warning.

## Batch Conversion

Use the batch CLI when you want Docling `DocumentConverter.convert_all` across
multiple files:

```bash
python -m ingest_orquestator_server.cli batch sample-inputs \
  --pipeline standard \
  --profile rag_ready \
  --output-dir .data/outputs
```
