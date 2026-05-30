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
python -m pip install -r requirements-vllm.txt
python -m pip install --no-deps -e .

INGEST_DOCLING_ACCELERATOR_DEVICE=cuda \
INGEST_DOCLING_NUM_THREADS=8 \
python -m ingest_orquestator_server.cli parse /path/to/document.pdf --output-dir .data/outputs
```

The default GPU dependency set includes SuryaOCR on supported Linux hosts.
SuryaOCR is GPL-3.0-only, requires Python 3.12+ on Linux, and is loaded by
Docling as an external plugin. If the plugin is not available, set
`INGEST_DOCLING_PDF_OCR_ENGINE=auto` to use Docling's built-in OCR selection.
FlashAttention-2 is optional; see the NVIDIA GPU venv tutorial before enabling
it.
vLLM is installed through `requirements-vllm.txt` and is used only for Docling
VLM stages/models documented as vLLM-capable.

SuryaOCR currently requires `transformers>=4.57,<5`. If an existing venv has
Transformers 5.x, reinstall the pinned dependency set:

```bash
python -m pip install --upgrade --force-reinstall "transformers>=4.57,<5"
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

This is the fix for SuryaOCR failures like
`AttributeError: 'SuryaDecoderConfig' object has no attribute 'pad_token_id'`.

For an A100 80GB CUDA 13 profile, use the checked-in
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

The default Dockerfile remains CPU-portable. For NVIDIA GPU hosts, use the GPU override:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
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
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build \
  --build-arg PYTORCH_CUDA_IMAGE=pytorch/pytorch:2.12.0-cuda13.2-cudnn9-runtime
```

## Configuration Reference

```text
INGEST_DOCLING_ACCELERATOR_DEVICE=auto
INGEST_DOCLING_NUM_THREADS=4
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false
INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true
INGEST_DOCLING_PIPELINE=standard
INGEST_DOCLING_VLM_MODEL=granite_vision
INGEST_DOCLING_VLM_RESPONSE_FORMAT=markdown
INGEST_DOCLING_VLM_RUNTIME=vllm
INGEST_DOCLING_VLLM_FALLBACK_RUNTIME=transformers
INGEST_DOCLING_VLLM_FALLBACK_ON_UNSUPPORTED=true
INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS=false
INGEST_DOCLING_PDF_DO_OCR=true
INGEST_DOCLING_PDF_OCR_ENGINE=suryaocr
INGEST_DOCLING_PDF_OCR_LANGUAGES=en
INGEST_DOCLING_PDF_OCR_USE_GPU=true
INGEST_DOCLING_PDF_DO_TABLE_STRUCTURE=true
INGEST_DOCLING_PDF_LAYOUT_MODEL=docling-layout-heron-101
INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND=tableformer
INGEST_DOCLING_PDF_TABLE_STRUCTURE_MODE=accurate
INGEST_DOCLING_PDF_TABLE_DO_CELL_MATCHING=true
INGEST_DOCLING_PDF_TABLE_STRUCTURE_VLM_MODEL=granite-vision-4.1-4b
INGEST_DOCLING_PDF_DO_PICTURE_CLASSIFICATION=true
INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET=document_figure_classifier_v2
INGEST_DOCLING_PDF_DO_PICTURE_DESCRIPTION=true
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL=granite_vision
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_RUNTIME=vllm
INGEST_DOCLING_PDF_DO_CODE_ENRICHMENT=true
INGEST_DOCLING_PDF_DO_FORMULA_ENRICHMENT=true
INGEST_DOCLING_PDF_CODE_FORMULA_PRESET=codeformulav2
INGEST_DOCLING_PDF_OCR_BATCH_SIZE=4
INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE=4
INGEST_DOCLING_PDF_TABLE_BATCH_SIZE=4
INGEST_DOCLING_PDF_QUEUE_MAX_SIZE=100
```

Use `INGEST_DOCLING_ACCELERATOR_DEVICE=cuda` for NVIDIA GPUs. Use `auto` to let Docling choose.

Use `--pipeline vlm` or `pipeline=vlm` only for PDF and image inputs in v1.2.
For details, see [`docs/docling-ingestion.md`](docling-ingestion.md).
For vLLM runtime details, see
[`docs/docling-vllm-migration.md`](docling-vllm-migration.md).

`INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true` should only be enabled when the
environment has a compatible `flash-attn` installation and the GPU architecture
supports it. The checked-in GPU profile keeps it disabled by default.

The default table structure backend remains TableFormer accurate mode with cell
matching. To test Docling's standard-pipeline Granite Vision table backend:

```bash
INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND=granite_vision
INGEST_DOCLING_PDF_TABLE_STRUCTURE_VLM_MODEL=granite-vision-4.1-4b
```
