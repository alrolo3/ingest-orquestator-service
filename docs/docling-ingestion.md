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

## Pipeline Matrix

| Input format | `standard` | `vlm` |
| --- | --- | --- |
| PDF | yes | yes |
| Image | yes | yes |
| DOCX, PPTX, HTML, MD, XLSX, CSV | yes | no |
| JSON Docling, AsciiDoc, LaTeX, VTT, XML formats | yes | no |

`pipeline=auto` resolves to `standard` in v1.2. Pre-rendering Office or HTML
documents to force VLM mode is deferred to a later milestone.

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

