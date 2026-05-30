# Docling Model Runtime Matrix

This matrix tracks which loaded Docling models can use vLLM in this service.

Source references:

- https://docling-project.github.io/docling/reference/document_converter/
- https://docling-project.github.io/docling/usage/model_catalog/

## VLM Convert

| Preset | Model | vLLM | Service behavior |
| --- | --- | --- | --- |
| `granite_docling` | Granite-Docling-258M | No | Use Docling default/Transformers/MLX/API path. |
| `smoldocling` | SmolDocling-256M | No | Use Docling default/Transformers/MLX path. |
| `deepseek_ocr` | DeepSeek-OCR-3B | No | API-oriented preset; not used for inline vLLM. |
| `granite_vision` | Granite-Vision-3.3-2B | Yes | Supported vLLM full-page conversion preset. |
| `pixtral` | Pixtral-12B | No | Use Transformers/MLX path. |
| `got_ocr` | GOT-OCR-2.0 | No | Use Transformers path. |
| `phi4` | Phi-4-Multimodal | Yes | Supported vLLM full-page conversion preset. |
| `qwen` | Qwen2.5-VL-3B-Instruct | No | Use Transformers/MLX path. |
| `nanonets_ocr2` | Nanonets-OCR2-3B | Yes | Supported vLLM full-page conversion preset. |
| `gemma_12b` | Gemma-3-12B | No | MLX-only in Docling catalog. |
| `gemma_27b` | Gemma-3-27B | No | MLX-only in Docling catalog. |
| `dolphin` | Dolphin | No | Use Transformers path. |

## Picture Description

| Preset | Model | vLLM | Service behavior |
| --- | --- | --- | --- |
| `smolvlm` | SmolVLM-256M | No | Use Transformers/MLX/API fallback. |
| `granite_vision` | Granite-Vision-3.3-2B | Yes | Supported vLLM picture-description preset. |
| `pixtral` | Pixtral-12B | No | Use Transformers/MLX fallback. |
| `qwen` | Qwen2.5-VL-3B-Instruct | No | Use Transformers/MLX fallback. |
| `Qwen/Qwen3-VL-8B-Instruct` | Qwen3-VL-8B-Instruct | Unverified | Defaults to Transformers fallback. Can be tested with `INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS=true`. |

## Other Loaded Models

| Stage | Model | Runtime | vLLM Migration |
| --- | --- | --- | --- |
| Layout | `docling-layout-heron-101` | `docling-ibm-models` | Not applicable. |
| OCR | `suryaocr` | SuryaOCR/PyTorch | Not applicable. |
| Table structure | TableFormer accurate | `docling-ibm-models` | Not applicable. |
| Table structure VLM | `granite-vision-4.1-4b` | Transformers | Not vLLM in current Docling catalog. |
| Picture classifier | `DocumentFigureClassifier-v2.5` | Transformers image classification | Not applicable. |
| Code/formula | `CodeFormulaV2` | Transformers | Not vLLM in current Docling catalog. |

## Runtime Policy

The service resolves runtime per stage:

1. If a stage/model is documented as vLLM-capable and runtime is `vllm` or
   `auto`, use vLLM.
2. If the model is unsupported and fallback is enabled, use
   `INGEST_DOCLING_VLLM_FALLBACK_RUNTIME`.
3. If fallback is disabled, reject the configuration before model load.
4. If `INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS=true`, custom repository ids
   may be attempted through Docling's inline vLLM path and must be validated by
   GPU smoke tests.
