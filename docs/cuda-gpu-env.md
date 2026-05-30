# CUDA GPU Environment Profile

`env-cuda-gpu` is a checked-in environment profile for high-throughput parsing on
an NVIDIA A100 80GB host with a CUDA 13 PyTorch runtime.

It is intentionally separate from `.env`. Keep `.env` local for machine-specific
overrides and copy from this profile when needed.

## Use Locally

Create a virtual environment and install a CUDA-enabled PyTorch runtime first:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

Use the official PyTorch selector for the exact command that matches the host
driver/runtime. Verify CUDA before continuing:

```bash
python - <<'PY'
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
PY
```

Then install the default deployment requirements:

```bash
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

The default GPU install path includes SuryaOCR. FlashAttention-2 is optional and
is not installed by default because it often requires a long source build.
SuryaOCR requires `transformers>=4.57,<5`; this keeps Qwen3-VL support while
avoiding a SuryaOCR runtime failure with Transformers 5.x.

To enable FlashAttention-2, install it explicitly after confirming that `nvcc`
matches `torch.version.cuda`:

```bash
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST="8.0"
export MAX_JOBS=4

python -m pip install --no-build-isolation --no-cache-dir -r requirements-flash-attn.txt
```

Then set this in `.env`:

```text
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true
```

Load the profile and run the API:

```bash
set -a
source env-cuda-gpu
set +a

python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Or run the CLI:

```bash
set -a
source env-cuda-gpu
set +a

python -m ingest_orquestator_server.cli parse /path/to/document.pdf --output-dir .data/outputs
```

## Verify The Runtime

Check CUDA and the selected GPU:

```bash
python - <<'PY'
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.get_device_name(0))
print(torch.cuda.get_device_capability(0))
PY
```

Check FlashAttention-2 if enabled:

```bash
python - <<'PY'
import flash_attn

print(flash_attn.__version__)
PY
```

If Docling fails while loading a VLM with FlashAttention enabled, first set:

```bash
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false
```

That falls back to PyTorch SDPA while keeping CUDA enabled.

## Profile Defaults

The profile chooses:

- `INGEST_DOCLING_ACCELERATOR_DEVICE=cuda`
- `INGEST_DOCLING_NUM_THREADS=32`
- `INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false`
- `INGEST_PROFILE=rag_ready`
- Docling HybridChunker enabled with `INGEST_CHUNK_MAX_TOKENS=1024`
- confidence output enabled
- SuryaOCR on GPU
- standard pipeline layout model `docling-layout-heron-101`
- TableFormer accurate mode with cell matching
- picture classification and picture description enabled
- code and formula enrichment enabled
- OCR/layout/table batch sizes set to `32`
- queue size set to `512`

These values are aggressive for an A100 80GB. If GPU memory spikes or the
process becomes less stable under concurrent requests, reduce the three batch
sizes from `32` to `16`.

## FlashAttention 3/4

For this service on A100, use FlashAttention-2.

Docling currently exposes this through
`INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true`. In the installed Docling code,
that flag maps Transformers model loads to:

```python
_attn_implementation="flash_attention_2"
```

There is no service-level config for FlashAttention-3 or FlashAttention-4 today.

FlashAttention-3 targets Hopper GPUs such as H100/H800. FlashAttention-4 is
optimized for Hopper and Blackwell through the new `flash-attn-4` package. They
are not the best fit for an A100, and Docling does not currently select them
from this service's configuration.

## Docker Notes

The GPU Dockerfile already uses the CUDA 13.2 PyTorch image and installs the
default GPU requirements from `requirements.txt`.

Then run the GPU compose profile:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```
