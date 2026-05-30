# Ingest Orquestator Server

`ingest-orquestator-server` is a small Docling-based ingestion service. The first MVP is intentionally narrow:

```text
ingest file -> parse with Docling -> output Markdown, text, raw JSON, normalized JSON
```

It does not include chunking, embeddings, vector storage, or RAG query APIs yet.

## What It Provides

- FastAPI service with a synchronous file ingestion endpoint.
- CLI command for local parser-only runs.
- Parser interface with a Docling implementation.
- Java-style module layout with separate model, service, adapter, and route files.
- Normalized document model for later chunking and indexing work.
- Local filesystem storage for uploaded files and parser outputs.
- Docker and Compose resources for running the service.

## Requirements

- Python 3.11, 3.12, or 3.13.
- `pip` and `venv` for the standard local setup.

Docling can download or initialize parsing models on first use, so the first parse may take longer than later runs.
The default OCR engine is SuryaOCR, which Docling loads through the external
`docling-surya` plugin. That plugin requires Python 3.12+ on Linux and is
GPL-3.0-only. For local development on another platform, set
`INGEST_DOCLING_PDF_OCR_ENGINE=auto`.

## Local Setup With Venv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

For the default SuryaOCR configuration on a supported Linux host:

```bash
python -m pip install -e ".[surya]"
```

For a portable local run without SuryaOCR:

```bash
INGEST_DOCLING_PDF_OCR_ENGINE=auto uvicorn ingest_orquestator_server.main:app --reload
```

Run the API:

```bash
uvicorn ingest_orquestator_server.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Stop the API with `Ctrl+C`.

## API Usage

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?include_document=false" \
  -F "file=@/path/to/document.pdf"
```

The response includes the parser status and the output file paths.

Check a persisted ingestion job:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}"
```

Download outputs:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/chunks"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/normalized"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/markdown"
```

## CLI Usage

```bash
ingest-orquestator parse /path/to/document.pdf --parser docling --output-dir .data/outputs
```

Each parse creates a document-specific output directory containing:

- `raw_docling.json`
- `normalized.json`
- `document.md`
- `document.txt`
- `document.html`, when Docling can export HTML
- `chunks.json`
- `manifest.json`

Clean old local artifacts:

```bash
ingest-orquestator cleanup --older-than-days 30 --dry-run
ingest-orquestator cleanup --older-than-days 30 --delete
```

## Development Setup

For tests and linting, install the development extras into the same virtual environment:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

If you prefer `uv`, the equivalent setup is:

```bash
uv sync --extra dev --python 3.12
uv run pytest
```

## Configuration

Configuration uses environment variables with the `INGEST_` prefix.

```bash
cp .env.example .env
```

Useful defaults:

```text
INGEST_SERVICE_NAME=ingest-orquestator-server
INGEST_STORAGE_DIR=.data
INGEST_MAX_UPLOAD_SIZE_MB=100
INGEST_ALLOWED_UPLOAD_EXTENSIONS=.pdf,.md,.markdown,.txt,.html,.htm,.docx,.pptx
INGEST_CHUNK_SIZE_CHARS=1200
INGEST_CHUNK_OVERLAP_CHARS=150
INGEST_RETENTION_DAYS=30
INGEST_DOCLING_ACCELERATOR_DEVICE=auto
INGEST_DOCLING_NUM_THREADS=4
INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true
INGEST_DOCLING_PDF_LAYOUT_MODEL=docling-layout-heron-101
INGEST_DOCLING_PDF_OCR_ENGINE=suryaocr
INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND=tableformer
INGEST_DOCLING_PDF_TABLE_STRUCTURE_MODE=accurate
INGEST_DOCLING_PDF_TABLE_DO_CELL_MATCHING=true
INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET=document_figure_classifier_v2
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_PDF_CODE_FORMULA_PRESET=codeformulav2
```

The standard PDF pipeline is used. The optional Granite Vision table structure
backend can be selected with:

```bash
INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND=granite_vision
INGEST_DOCLING_PDF_TABLE_STRUCTURE_VLM_MODEL=granite-vision-4.1-4b
```

For NVIDIA GPUs, run with a CUDA-enabled PyTorch environment and set:

```bash
INGEST_DOCLING_ACCELERATOR_DEVICE=cuda
```

See [docs/gpu.md](docs/gpu.md) for Docker Compose GPU usage and batch-size tuning.
For the A100 80GB CUDA 13 performance profile, use
[env-cuda-gpu](env-cuda-gpu) with [docs/cuda-gpu-env.md](docs/cuda-gpu-env.md).

## Docker

```bash
docker compose up --build
```

The API will listen on:

```text
http://127.0.0.1:8000
```

For NVIDIA GPU hosts:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

## Next Milestones

1. Add asynchronous worker execution for long-running PDFs.
2. Add embeddings and a vector database adapter.
3. Add a second parser backend for advanced PDFs.
