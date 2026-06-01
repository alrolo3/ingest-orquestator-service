# Linux CPU Venv Setup

Use this path for Linux hosts without NVIDIA GPU acceleration. This tutorial
installs only the base project dependencies and uses the CPU-safe environment
file.

## 1. Install Python Venv Support

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev build-essential
```

If your distribution provides Python 3.11 or 3.13 instead, that is also within
the supported project range.

## 2. Create The Virtual Environment

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

## 3. Install The CPU Development Package

Install from `pyproject.toml` directly:

```bash
python -m pip install -e .
```

Do not use `requirements.txt` for CPU-only Linux. The default requirements file
includes SuryaOCR on supported Linux hosts. That is intended for GPU
deployments.

## 4. Use The CPU Environment

Create a local `.env` from the checked-in CPU environment:

```bash
cp env-cpu .env
```

The CPU environment uses Docling's automatic OCR selection and disables OCR GPU
usage:

```text
INGEST_DOCLING_ACCELERATOR_DEVICE=cpu
INGEST_DOCLING_PDF_OCR_ENGINE=auto
INGEST_DOCLING_PDF_OCR_USE_GPU=false
```

## 5. Run The API

```bash
python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

## 6. Run An API Smoke Test

```bash
printf "# CPU smoke test\n\nHello from Linux.\n" > /tmp/ingest-smoke.md
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/tmp/ingest-smoke.md"
)
echo "$response"
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Expected result: the initial response is `parser_queued`; after parser and
dispatcher completion the job reaches `completed` and a new output directory is
available under `.data/outputs`.

## Troubleshooting

If you accidentally installed `requirements.txt` and pulled GPU-only packages,
remove the environment and start again with the base install:

```bash
deactivate 2>/dev/null || true
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
cp env-cpu .env
```
