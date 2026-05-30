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

## Local Setup With Venv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
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

## CLI Usage

```bash
ingest-orquestator parse /path/to/document.pdf --output-dir .data/outputs
```

Each parse creates a document-specific output directory containing:

- `raw_docling.json`
- `normalized.json`
- `document.md`
- `document.txt`
- `document.html`, when Docling can export HTML
- `manifest.json`

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
INGEST_DOCLING_ACCELERATOR_DEVICE=auto
INGEST_DOCLING_NUM_THREADS=4
```

For NVIDIA GPUs, run with a CUDA-enabled PyTorch environment and set:

```bash
INGEST_DOCLING_ACCELERATOR_DEVICE=cuda
```

See [docs/gpu.md](docs/gpu.md) for Docker Compose GPU usage and batch-size tuning.

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

1. Add asynchronous job state with SQLite or PostgreSQL.
2. Add chunking from normalized elements.
3. Add embeddings and a vector database adapter.
4. Add a second parser backend for advanced PDFs.
