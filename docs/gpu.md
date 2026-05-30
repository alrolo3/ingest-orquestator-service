# NVIDIA GPU Configuration

Docling can run model inference with explicit accelerator options. The service exposes those options with `INGEST_` environment variables.

## Local CUDA Host

Install the project in an environment that has a CUDA-enabled PyTorch build, then choose the CUDA accelerator:

```bash
INGEST_DOCLING_ACCELERATOR_DEVICE=cuda \
INGEST_DOCLING_NUM_THREADS=8 \
uv run ingest-orquestator parse /path/to/document.pdf --output-dir .data/outputs
```

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
INGEST_DOCLING_PDF_DO_OCR=true
INGEST_DOCLING_PDF_DO_TABLE_STRUCTURE=true
INGEST_DOCLING_PDF_OCR_BATCH_SIZE=4
INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE=4
INGEST_DOCLING_PDF_TABLE_BATCH_SIZE=4
INGEST_DOCLING_PDF_QUEUE_MAX_SIZE=100
```

Use `INGEST_DOCLING_ACCELERATOR_DEVICE=cuda` for NVIDIA GPUs. Use `auto` to let Docling choose.

`INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true` should only be enabled when the image has a compatible `flash-attn` installation and the GPU architecture supports it.
