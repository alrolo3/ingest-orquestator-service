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
includes SuryaOCR, FlashAttention-2, and the build helpers required by
FlashAttention-2.

```bash
MAX_JOBS=8 python -m pip install --no-build-isolation -r requirements.txt
python -m pip install --no-deps -e .
```

If `flash-attn` fails to build, confirm that PyTorch is already installed in the
same venv and that this check prints `True`:

```bash
python - <<'PY'
import torch

print(torch.cuda.is_available())
PY
```

## 6. Use The A100 CUDA Profile

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

## 7. Verify GPU Packages

```bash
python - <<'PY'
import docling_surya
import flash_attn

print("docling_surya", docling_surya.__name__)
print("flash_attn", flash_attn.__version__)
PY
```

## 8. Run The API

```bash
python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

## 9. Run A CLI Smoke Test

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
INGEST_DOCLING_CUDA_USE_FLASH_ATTENTION2=true
```

If a VLM fails during startup or model loading, set this to `false` in `.env`.
That keeps CUDA enabled and falls back to PyTorch SDPA for attention.
