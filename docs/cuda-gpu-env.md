# CUDA GPU Environment Profile

`env-cuda-gpu` is a checked-in environment profile for high-throughput parsing on
an NVIDIA A100 80GB host with a CUDA 13 PyTorch runtime.

It is intentionally separate from `.env`. Keep `.env` local for machine-specific
overrides and copy from this profile when needed.

## Use Locally

Install the GPU/runtime extras first:

```bash
uv sync --extra surya --python 3.12
```

Install FlashAttention-2 into the same CUDA environment if you want
`INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true`:

```bash
uv pip install packaging psutil ninja
MAX_JOBS=8 uv pip install flash-attn --no-build-isolation
```

Load the profile and run the API:

```bash
set -a
source env-cuda-gpu
set +a

uv run uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Or run the CLI:

```bash
set -a
source env-cuda-gpu
set +a

uv run ingest-orquestator parse /path/to/document.pdf --output-dir .data/outputs
```

## Verify The Runtime

Check CUDA and the selected GPU:

```bash
uv run python - <<'PY'
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.get_device_name(0))
print(torch.cuda.get_device_capability(0))
PY
```

Check FlashAttention-2 if enabled:

```bash
uv run python - <<'PY'
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
- `INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true`
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

## FlashInfer And FlashAttention 3/4

For this service on A100, use FlashAttention-2.

Docling currently exposes this through
`INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true`. In the installed Docling code,
that flag maps Transformers model loads to:

```python
_attn_implementation="flash_attention_2"
```

There is no service-level config for FlashInfer, FlashAttention-3, or
FlashAttention-4 today.

FlashInfer is usable with CUDA 13 as a library, but it is not a drop-in
replacement for Docling's current Transformers attention setting. Using it here
would require a code change or a different VLM serving path that explicitly
integrates FlashInfer kernels.

FlashAttention-3 targets Hopper GPUs such as H100/H800. FlashAttention-4 is
optimized for Hopper and Blackwell through the new `flash-attn-4` package. They
are not the best fit for an A100, and Docling does not currently select them
from this service's configuration.

## Docker Notes

The GPU Dockerfile already uses the CUDA 13.2 PyTorch image and installs the
Surya extra. For FlashAttention-2 inside the image, extend the image with:

```dockerfile
RUN pip install --no-cache-dir packaging psutil ninja \
    && MAX_JOBS=8 pip install --no-cache-dir flash-attn --no-build-isolation
```

Then run the GPU compose profile:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```
