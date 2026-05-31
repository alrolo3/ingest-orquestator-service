# Docling Model Runtime Matrix

This matrix tracks how the service routes Docling model stages after the
RemoteLLM rework.

Source references:

- https://docling-project.github.io/docling/reference/document_converter/
- https://docling-project.github.io/docling/reference/pipeline_options/
- https://docling-project.github.io/docling/usage/model_catalog/

## VLM Convert

| Runtime | Service behavior |
| --- | --- |
| `transformers` | Load the configured model locally through Docling inline VLM options. This remains the default for `env-cuda-gpu`. |
| `auto` | Resolve to local Transformers for predictable API-server behavior. |
| `auto_inline` | Use Docling auto-inline VLM engine selection with `prefer_vllm=false`. |
| `remote_llm` | Send VLM requests to an external OpenAI-compatible endpoint through Docling `ApiVlmOptions`. |

## Picture Description

| Runtime | Service behavior |
| --- | --- |
| `transformers` | Load the configured picture-description model locally through Docling picture-description options. |
| `auto` | Resolve to local Transformers. |
| `auto_inline` | Use Docling auto-inline engine selection with `prefer_vllm=false`. |
| `remote_llm` | Send picture-description requests to the external OpenAI-compatible endpoint through Docling `PictureDescriptionApiOptions`. |

## Other Loaded Models

| Stage | Model | Runtime | RemoteLLM Migration |
| --- | --- | --- | --- |
| Layout | `docling-layout-heron-101` | `docling-ibm-models` | Not applicable. |
| OCR | `suryaocr` | SuryaOCR/PyTorch | Not applicable. |
| Table structure | TableFormer accurate | `docling-ibm-models` | Not applicable. |
| Table structure VLM | `granite-vision-4.1-4b` | Transformers | Not routed through RemoteLLM by Docling's standard pipeline options today. |
| Picture classifier | `DocumentFigureClassifier-v2.5` | Transformers image classification | Not applicable. |
| Code/formula | `CodeFormulaV2` | Transformers | Not routed through RemoteLLM by Docling's current enrichment options. |

## Runtime Policy

The service resolves runtime per stage:

1. `remote_llm` means "call an external endpoint", regardless of the model id.
2. Local `transformers` stays available for GPU hosts that want Docling to load
   Qwen3 directly.
3. Non-generative stages stay on their Docling/engine-specific runtimes.
4. Remote endpoint compatibility is checked with `/health/remote-llm` and,
   optionally, startup validation.
