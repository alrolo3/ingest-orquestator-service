# Linux NVIDIA GPU Venv Setup

Use this path for Linux hosts with an NVIDIA GPU. The checked-in
`env-cuda-gpu` profile is tuned for an A100 80GB with a CUDA 13 PyTorch runtime.

## 1. Verify The Host GPU

```bash
nvidia-smi
```

Expected result: the NVIDIA driver reports the GPU and CUDA driver capability.
For strict single-GPU placement, the profile uses:

```text
CUDA_VISIBLE_DEVICES=0
NVIDIA_VISIBLE_DEVICES=0
```

Change those values in your local `.env` if the service should use another GPU.

## 2. Install Python Venv Support

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev build-essential
```

## 3. Create The Virtual Environment

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

## 4. Install A CUDA-Enabled PyTorch Runtime

Install a PyTorch build that matches your CUDA runtime. For CUDA 13 hosts, use
the current command from the official PyTorch selector for your driver/runtime.

After installing PyTorch, verify CUDA before continuing:

```bash
python - <<'PY'
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
print(torch.cuda.get_device_capability(0))
PY
```

Expected result:

- `torch.cuda.is_available()` prints `True`
- `torch.version.cuda` reports a CUDA 13.x runtime for a CUDA 13 setup
- A100 reports compute capability `(8, 0)`

Do not continue until PyTorch can see the GPU.

## 5. Install The GPU Requirements

Install the default deployment requirements. On supported Linux hosts this
includes SuryaOCR. FlashAttention-2 is optional and is not installed by default
because it often builds from source and requires the CUDA toolkit compiler to
match the installed PyTorch CUDA runtime.
The requirements pin `transformers>=4.57,<5` because SuryaOCR is not compatible
with Transformers 5.x, while Qwen3-VL is supported in Transformers 4.57+.

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-vllm.txt
python -m pip install --no-deps -e .
```

If you previously installed Transformers 5.x in this venv, force the compatible
range before retrying SuryaOCR:

```bash
python -m pip install --upgrade --force-reinstall "transformers>=4.57,<5"
python -m pip install -r requirements.txt
```

Verify the active version:

```bash
python - <<'PY'
import transformers

print(transformers.__version__)
PY
```

Expected result: a 4.57+ version lower than 5.0. If SuryaOCR previously failed
with `SuryaDecoderConfig` missing `pad_token_id`, this version mismatch was the
cause.

## 6. Verify vLLM

The checked-in GPU profile defaults to Qwen3 through Transformers. vLLM remains
available for explicit experiments with supported presets or unverified custom
models.

```bash
python - <<'PY'
import vllm

print("vllm", vllm.__version__)
PY
```

If vLLM should be disabled for troubleshooting, set:

```text
INGEST_DOCLING_VLM_RUNTIME=transformers
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_RUNTIME=transformers
```

## 7. Optional: Enable FlashAttention-2

Skip this section unless you explicitly want Docling to load local VLMs with
FlashAttention-2. The CUDA toolkit reported by `nvcc -V` must match
`torch.version.cuda`. A driver that reports CUDA 13.2 can still run a CUDA 12.8
PyTorch build, but building FlashAttention for that PyTorch build requires a
CUDA 12.8 toolkit.

Verify the CUDA versions:

```bash
python - <<'PY'
import torch
from torch.utils.cpp_extension import CUDA_HOME

print("torch:", torch.__version__)
print("torch cuda:", torch.version.cuda)
print("CUDA_HOME:", CUDA_HOME)
PY
nvcc -V
```

For A100, compile only the `sm_80` kernels to avoid building unnecessary Hopper
and Blackwell kernels:

```bash
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST="8.0"
export MAX_JOBS=4

python -m pip install --no-build-isolation --no-cache-dir -r requirements-flash-attn.txt
```

Then enable it in your local `.env`:

```text
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true
```

Verify the package:

```bash
python - <<'PY'
import flash_attn

print(flash_attn.__version__)
PY
```

## 8. Use The A100 CUDA Profile

Create a local `.env` from the checked-in GPU profile:

```bash
cp env-cuda-gpu .env
```

For non-A100 GPUs, start with these lower batch sizes:

```text
INGEST_DOCLING_PDF_OCR_BATCH_SIZE=8
INGEST_DOCLING_PDF_LAYOUT_BATCH_SIZE=8
INGEST_DOCLING_PDF_TABLE_BATCH_SIZE=8
INGEST_DOCLING_PDF_QUEUE_MAX_SIZE=128
```

## 9. Verify GPU Packages

```bash
python - <<'PY'
import docling_surya

print("docling_surya", docling_surya.__name__)
PY
```

## 10. Run The API

```bash
python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

## 11. Run A CLI Smoke Test

```bash
printf "# GPU smoke test\n\nHello from NVIDIA.\n" > /tmp/ingest-smoke.md
python -m ingest_orquestator_server.cli parse /tmp/ingest-smoke.md --parser docling --output-dir .data/outputs
```

For a real PDF parse:

```bash
python -m ingest_orquestator_server.cli parse /path/to/document.pdf --parser docling --output-dir .data/outputs
```

## FlashAttention Notes

The service exposes Docling's current FlashAttention switch through:

```text
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=false
```

The checked-in GPU profile keeps this disabled by default. Set it to `true` only
after `requirements-flash-attn.txt` installs successfully.
