# macOS CPU Venv Setup

Use this path for local development on macOS without NVIDIA GPU acceleration.
This tutorial does not install SuryaOCR or FlashAttention.

## 1. Create The Virtual Environment

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

If `python3.12` is not available, install Python 3.12 first, then rerun the
commands above.

## 2. Install The CPU Development Package

Install the project from `pyproject.toml` directly:

```bash
python -m pip install -e .
```

Do not use `requirements.txt` for this macOS CPU setup. The requirements file is
the default deploy dependency set and contains Linux-only GPU packages behind
environment markers.

## 3. Use The CPU Environment

Create a local `.env` from the checked-in CPU environment:

```bash
cp env-cpu .env
```

The CPU environment selects:

- `INGEST_DOCLING_ACCELERATOR_DEVICE=cpu`
- `INGEST_DOCLING_PDF_OCR_ENGINE=auto`
- picture description disabled
- code and formula enrichment disabled
- small batch sizes

Those choices avoid loading large VLMs on a CPU-only machine.

## 4. Run The API

```bash
python -m uvicorn ingest_orquestator_server.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Check health:

```bash
curl http://127.0.0.1:8000/health
```

## 5. Run An API Smoke Test

In another terminal:

```bash
source .venv/bin/activate
printf "# CPU smoke test\n\nHello from macOS.\n" > /tmp/ingest-smoke.md
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/tmp/ingest-smoke.md"
)
echo "$response"
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Expected result: the initial response is `parser_queued`; after parser and
dispatcher completion the job reaches `completed` and a new output directory
contains `document.md`, `document_metadata.json`, and `rag_chunks.jsonl`.
`document.html` is created only when `include_html=true` is sent with the
ingest request.

## Troubleshooting

If the service tries to use SuryaOCR or CUDA, verify `.env` was created from
`env-cpu`:

```bash
python - <<'PY'
from ingest_orquestator_server.config import Settings

s = Settings()
print(s.docling_accelerator_device)
print(s.docling_pdf_ocr_engine)
print(s.docling_pdf_do_picture_description)
PY
```

Expected output:

```text
cpu
auto
False
```
