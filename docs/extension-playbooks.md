# Extension Playbooks

## Add A Parser Adapter

1. Implement the `DocumentParser` port.
2. Return a `ParseOutput` with raw output, Markdown, text, and normalized
   `ParsedDocument`.
3. Register the parser in the parser registry factory.
4. Add contract tests using the shared parser contract fixture.
5. Document required runtime dependencies and local smoke commands.

## Add A Docling OCR Plugin

Docling discovers external plugins through the `docling` Python entry point.
The plugin package should expose an `ocr_engines()` factory that returns OCR
model classes compatible with Docling's OCR model interfaces.

Checklist:

1. Add the plugin package dependency.
2. Keep `INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true` where the plugin should
   be loaded.
3. Set `INGEST_DOCLING_PDF_OCR_ENGINE=<plugin-engine-id>`.
4. Add a unit test for engine discovery and an optional integration smoke test.
5. Document GPU/CPU requirements and model artifact download behavior.

Docling plugin reference:

- https://docling-project.github.io/docling/concepts/plugins/

## Add A Pipeline Or VLM Runtime

1. Check the `DocumentConverter` reference for the correct `FormatOption`,
   `pipeline_cls`, and `pipeline_options` combination.
2. Add settings under the Docling VLM/common config group.
3. Add support matrix validation before converter construction.
4. Add unit tests that construct options without loading model weights.
5. Add an optional integration smoke test gated by an env flag when model
   execution requires GPU or large downloads.

