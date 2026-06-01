# Docling Model Runtime Matrix

This matrix tracks where Docling-related model work runs. VLM stages are always
routed to RemoteLLM; the backend does not load local VLM models.

Source references:

- https://docling-project.github.io/docling/reference/document_converter/
- https://docling-project.github.io/docling/reference/pipeline_options/
- https://docling-project.github.io/docling/usage/model_catalog/

## VLM Convert

| Stage | Service behavior |
| --- | --- |
| Full-page VLM conversion | Sends requests to an external OpenAI-compatible endpoint through Docling `ApiVlmOptions`. |

## Picture Description

| Stage | Service behavior |
| --- | --- |
| Standard-pipeline picture descriptions | Sends requests to the external OpenAI-compatible endpoint through Docling `PictureDescriptionApiOptions`. |

## Other Loaded Models

| Stage | Model | Runtime | RemoteLLM Migration |
| --- | --- | --- | --- |
| Layout | `docling-layout-heron-101` | `docling-ibm-models` | Not applicable. |
| OCR | `suryaocr` | SuryaOCR/PyTorch | Not applicable. |
| Table structure | TableFormer accurate | `docling-ibm-models` | Not applicable. |
| Picture classifier | `DocumentFigureClassifier-v2.5` | Transformers image classification | Not applicable. |

## Runtime Policy

The service resolves runtime per stage:

1. VLM stages call an external endpoint, regardless of the model id.
2. Local backend VLM loading is intentionally not supported.
3. Non-generative stages stay on their Docling/engine-specific runtimes.
4. Remote endpoint compatibility is checked with `/health/remote-llm` and,
   optionally, startup validation.
