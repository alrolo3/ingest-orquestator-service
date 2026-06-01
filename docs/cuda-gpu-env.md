# CUDA GPU Environment

`env-cuda-gpu` is a checked-in environment file for high-throughput parsing on
an NVIDIA A100 80GB host with a CUDA 13 PyTorch runtime.

It is intentionally separate from `.env`. Keep `.env` local for machine-specific
overrides and copy from this file when needed.

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
SuryaOCR requires `transformers>=4.57,<5`; this keeps SuryaOCR within the
currently supported dependency range while avoiding a runtime failure with
Transformers 5.x.
RemoteLLM calls go through an external OpenAI-compatible endpoint. Install
`requirements-vllm.txt` only in the separate environment that runs `vllm serve`,
not as part of the API service install.

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

Load the environment and run the API:

```bash
set -a
source env-cuda-gpu
set +a

python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Submit a document through the API:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/path/to/document.pdf"
)
echo "$response"
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
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

If Docling fails while running a GPU model with FlashAttention enabled, first set:

```bash
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false
```

That falls back to PyTorch SDPA while keeping CUDA enabled.

## Environment Defaults

The environment chooses:

- `INGEST_DOCLING_ACCELERATOR_DEVICE=cuda`
- `INGEST_DOCLING_NUM_THREADS=32`
- `INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false`
- request-level Docling chunking defaults to disabled, with page chunking as
  the compatibility fallback and `INGEST_CHUNK_MAX_TOKENS=1024` for token
  chunking requests
- confidence output enabled
- Docling engine cache enabled, no idle eviction, and compatible conversion
  batching up to 5 documents
- local XBRL taxonomy fetch enabled, remote XBRL fetch disabled
- SuryaOCR on GPU
- full-page VLM conversion defaults to `Qwen/Qwen3-VL-8B-Instruct` through RemoteLLM
- standard pipeline layout model `docling-layout-heron-101`
- TableFormer accurate mode with cell matching
- picture classification and picture description enabled
- picture description defaults to `Qwen/Qwen3-VL-8B-Instruct` through RemoteLLM
- OCR/layout/table batch sizes set to `32`
- queue size set to `512`
- parser document concurrency set to two independent parser processes with one
  actor thread per process

These values are aggressive for an A100 80GB. If GPU memory spikes or the
process becomes less stable under concurrent requests, reduce
`INGEST_PARSER_PROCESS_COUNT` first, then reduce the three Docling batch sizes
from `32` to `16`.

## RemoteLLM

The GPU environment uses RemoteLLM for Qwen3 so the model is hosted by one
external inference server instead of being loaded inside each API worker:

```text
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

Configure the external inference server endpoint with:

```text
INGEST_DOCLING_REMOTE_LLM_URL=http://127.0.0.1:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_ENABLED=true
```

RemoteLLM request concurrency is controlled by
`INGEST_DOCLING_REMOTE_LLM_CONCURRENCY`. Parser document concurrency is
controlled separately by `INGEST_PARSER_PROCESS_COUNT`; each parser process can
use Docling's threaded PDF pipeline stages for its assigned document.

See [Docling RemoteLLM playbook](docling-remote-llm.md) and
[Docling model runtime matrix](docling-model-runtime-matrix.md). For API-side
engine caching and batching, see
[Docling engine lifecycle](docling-engine-lifecycle.md).

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

Then run the GPU compose overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```
