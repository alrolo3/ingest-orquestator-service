# NVIDIA GPU Configuration

Docling can run model inference with explicit accelerator options. The service exposes those options with `INGEST_` environment variables.

## Local CUDA Host

Install the project in a virtual environment that has a CUDA-enabled PyTorch
build, then choose the CUDA accelerator:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

# Install a CUDA-enabled torch build first, then install deployment requirements.
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .

python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/path/to/document.pdf"
)
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

The default GPU dependency set includes SuryaOCR on supported Linux hosts.
SuryaOCR is GPL-3.0-only, requires Python 3.12+ on Linux, and is loaded by
Docling as an external plugin. If the plugin is not available, set
`INGEST_DOCLING_PDF_OCR_ENGINE=auto` to use Docling's built-in OCR selection.
FlashAttention-2 is optional; see the NVIDIA GPU venv tutorial before enabling
it. RemoteLLM uses a separate OpenAI-compatible inference endpoint for VLM
calls; do not install vLLM in the API service venv unless this host also runs
the external inference server.

SuryaOCR imports OpenCV at runtime. On Ubuntu/Debian hosts, install the OpenCV
runtime libraries before starting the API or workers:

```bash
sudo apt-get install -y \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1
```

The Docker images install these packages and run `import cv2` during build so
missing native libraries such as `libxcb.so.1` fail fast.

SuryaOCR currently requires `transformers>=4.57,<5`. If an existing venv has
Transformers 5.x, reinstall the pinned dependency set:

```bash
python -m pip install --upgrade --force-reinstall "transformers>=4.57,<5"
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

This is the fix for SuryaOCR failures like
`AttributeError: 'SuryaDecoderConfig' object has no attribute 'pad_token_id'`.

For an A100 80GB CUDA 13 environment, use the checked-in
[`env-cuda-gpu`](../env-cuda-gpu) file and see
[`docs/cuda-gpu-env.md`](cuda-gpu-env.md).

For a full venv walkthrough, use
[`docs/tutorials/linux-nvidia-gpu-venv.md`](tutorials/linux-nvidia-gpu-venv.md).

To select a specific GPU, use a CUDA device string:

```bash
INGEST_DOCLING_ACCELERATOR_DEVICE=cuda:1
```

Docling notes that EasyOCR can ignore `cuda:N` and default to `cuda:0`, so prefer `CUDA_VISIBLE_DEVICES` when strict GPU placement matters:

```bash
CUDA_VISIBLE_DEVICES=1 INGEST_DOCLING_ACCELERATOR_DEVICE=cuda ...
```

## Docker Compose GPU Run

For a full platform deployment with RabbitMQ, API, workers, and the frontend,
use the NVIDIA GPU compose file:

```bash
docker compose -f docker-compose.nvidia-gpu.yml up --build
```

Requirements:

- NVIDIA driver installed on the host.
- NVIDIA Container Toolkit configured for Docker.
- A driver new enough for the CUDA runtime in the selected PyTorch image.

The GPU image defaults to CUDA 13.2:

```text
pytorch/pytorch:2.12.0-cuda13.2-cudnn9-runtime
```

Override it at build time if your host requires another CUDA/PyTorch combination:

```bash
docker compose -f docker-compose.nvidia-gpu.yml build \
  --build-arg PYTORCH_CUDA_IMAGE=pytorch/pytorch:2.12.0-cuda13.2-cudnn9-runtime
```

The older `docker-compose.yml` plus `docker-compose.gpu.yml` path still works
for backend-only testing. Prefer
[`docs/docker-compose-platform.md`](docker-compose-platform.md) for normal
platform deployment.

## Configuration Reference

```text
INGEST_DOCLING_ACCELERATOR_DEVICE=cuda
INGEST_DOCLING_NUM_THREADS=32
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false
INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true
INGEST_DOCLING_PIPELINE=standard
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_VLM_RESPONSE_FORMAT=markdown
INGEST_DOCLING_REMOTE_LLM_URL=http://localhost:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_PDF_OCR_ENGINE=suryaocr
INGEST_DOCLING_PDF_OCR_USE_GPU=true
INGEST_DOCLING_PDF_LAYOUT_MODEL=docling-layout-heron-101
INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND=tableformer
INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET=document_figure_classifier_v2
```

Use `INGEST_DOCLING_ACCELERATOR_DEVICE=cuda` for NVIDIA GPUs. Use `auto` to let Docling choose.
OCR is always enabled and defaults to English. Request-specific OCR languages
are selected through the ingest API. Docling engine caching, warmup behavior,
table mode/cell matching, picture descriptions, and pipeline batch sizes are
explicit settings. Parser document concurrency follows
`INGEST_PARSER_PROCESS_COUNT`; RemoteLLM concurrency follows
`INGEST_DOCLING_REMOTE_LLM_CONCURRENCY`.

Use `pipeline=vlm` only for PDF and image inputs.
For details, see [`docs/docling-ingestion.md`](docling-ingestion.md).
For RemoteLLM endpoint details, see
[`docs/docling-remote-llm.md`](docling-remote-llm.md).
For engine caching, warmup, batching, and GPU model reuse, see
[`docs/docling-engine-lifecycle.md`](docling-engine-lifecycle.md).

`INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true` should only be enabled when the
environment has a compatible `flash-attn` installation and the GPU architecture
supports it. The checked-in GPU environment keeps it disabled by default.

The default table structure backend remains TableFormer accurate mode with cell
matching.
