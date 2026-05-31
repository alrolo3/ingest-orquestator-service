# Docling vLLM Migration Playbook

This project supports vLLM for Docling stages where Docling exposes a vLLM
engine. It does not force vLLM onto non-VLM stages.

## Current Boundary

Docling's `DocumentConverter` accepts format-specific options through
`format_options`, which is the integration point used by this service for PDF,
image, XBRL, and VLM pipeline configuration:

- https://docling-project.github.io/docling/reference/document_converter/

Docling's model catalog shows that vLLM is available only for selected VLM
stages and presets:

- https://docling-project.github.io/docling/usage/model_catalog/

## vLLM-Capable Stages

| Stage | vLLM Strategy |
| --- | --- |
| Full-page VLM conversion | Supported for selected Docling presets such as `granite_vision`, `phi4`, and `nanonets_ocr2`. |
| Picture description | Supported for selected Docling presets, currently `granite_vision` in the service capability matrix. |

## Stages Not Migrated To vLLM

| Stage | Runtime | Reason |
| --- | --- | --- |
| Layout | `docling-ibm-models` | Object-detection stage, not a generative VLM. |
| OCR | Engine-specific | OCR engines such as SuryaOCR use their own PyTorch/runtime path. |
| TableFormer table structure | `docling-ibm-models` | Specialized table-structure model. |
| Granite Vision table structure | Transformers | Docling catalog currently lists the table-structure VLM path with Transformers. |
| Picture classifier | Transformers image classification | ViT classifier, not a generative VLM. |
| Code/formula extraction | Transformers/MLX | Docling catalog lists CodeFormulaV2 without vLLM support. |

## Install vLLM

Install base requirements first, then the optional vLLM requirements:

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements-vllm.txt
python -m pip install --no-deps -e .
```

Verify vLLM imports:

```bash
python - <<'PY'
import vllm

print("vllm:", vllm.__version__)
PY
```

## GPU Environment

The checked-in `env-cuda-gpu` environment defaults to Qwen3 through Transformers:

```bash
set -a
source env-cuda-gpu
set +a

python - <<'PY'
from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)

s = Settings()
print(resolve_vlm_convert_runtime(s))
print(resolve_picture_description_runtime(s))
PY
```

Expected defaults from `env-cuda-gpu`:

```text
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_VLM_RUNTIME=transformers
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_RUNTIME=transformers
```

## Fallback Policy

Unsupported or custom vLLM requests fall back by default:

```text
INGEST_DOCLING_VLLM_FALLBACK_ON_UNSUPPORTED=true
INGEST_DOCLING_VLLM_FALLBACK_RUNTIME=transformers
INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS=false
```

For example, `Qwen/Qwen3-VL-8B-Instruct` is a valid Transformers model in this
project, but it is not listed as a vLLM-capable Docling catalog preset. With the
default policy, a vLLM request for Qwen3 resolves to Transformers and records
the fallback reason in metadata.

To hard-fail instead:

```bash
INGEST_DOCLING_VLLM_FALLBACK_ON_UNSUPPORTED=false
```

To experiment with a custom repo id through Docling's vLLM inline path:

```bash
INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS=true
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_VLM_RUNTIME=vllm
INGEST_DOCLING_VLM_TRUST_REMOTE_CODE=false
INGEST_DOCLING_VLLM_GPU_MEMORY_UTILIZATION=0.9
INGEST_DOCLING_VLLM_CUDAGRAPH_MODE=NONE
INGEST_DOCLING_VLLM_MAX_MODEL_LEN=32768
INGEST_DOCLING_VLLM_MAX_NUM_BATCHED_TOKENS=4096
```

This should be treated as experimental until a GPU smoke test confirms model
load, output quality, and memory behavior.

For custom inline models, Docling uses a legacy inline vLLM path. This service
passes vLLM memory and batching controls through that path using Docling's
`extra_generation_config` allowlist.

If a custom model fails with a `trust_remote_code=True` error, inspect the model
repository first. If the repository is trusted, enable:

```bash
INGEST_DOCLING_VLM_TRUST_REMOTE_CODE=true
```

## Smoke Tests

Full-page VLM with vLLM:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=vlm" \
  -F "file=@sample-inputs/sample.pdf"
)
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Standard pipeline with vLLM picture descriptions:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@sample-inputs/qwen3-picture-description-smoke.pdf"
)
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Inspect runtime metadata:

```bash
python - <<'PY'
import json
from pathlib import Path

latest = max(Path(".data/outputs").iterdir(), key=lambda p: p.stat().st_mtime)
manifest = json.loads((latest / "manifest.json").read_text())
print(json.dumps(manifest["diagnostics"]["metadata"]["runtime"], indent=2))
PY
```

## Metadata

Runtime resolution is written into:

- `manifest.json` diagnostics metadata.
- `normalized.json` document metadata.
- `embedding_input.jsonl` record metadata.
- API response metadata.

Key fields:

```text
runtime.stages.vlm_convert.requested_runtime
runtime.stages.vlm_convert.resolved_runtime
runtime.stages.picture_description.requested_runtime
runtime.stages.picture_description.resolved_runtime
runtime.stages.*.fallback_reason
```
