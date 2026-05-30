# Ingest Orquestator Server

`ingest-orquestator-server` is a Docling-based ingestion service:

```text
ingest file -> parse with Docling -> normalized/chunked/embedding-ready output
```

It does not include vector storage or RAG query APIs yet.

## What It Provides

- FastAPI service with synchronous and background file ingestion.
- CLI command for local parser-only runs.
- Parser interface with a Docling implementation.
- Multi-format Docling `DocumentConverter` support.
- Java-style module layout with separate model, service, adapter, and route files.
- Normalized document, chunk, and embedding input outputs.
- Local filesystem storage for uploaded files and parser outputs.
- Docker and Compose resources for running the service.

## Requirements

- Python 3.11, 3.12, or 3.13.
- `pip` and `venv` for the standard local setup.

Docling can download or initialize parsing models on first use, so the first parse may take longer than later runs.
The default install uses `docling[xbrl]` so the sample XBRL fixture and XBRL
documents work without an extra install step.
The default OCR engine is SuryaOCR, which Docling loads through the external
`docling-surya` plugin. That plugin requires Python 3.12+ on Linux and is
GPL-3.0-only. It also requires `transformers>=4.57,<5`: the lower bound keeps
Qwen3-VL support, and the upper bound avoids a SuryaOCR incompatibility in
Transformers 5.x. For local development on another platform, set
`INGEST_DOCLING_PDF_OCR_ENGINE=auto`.

## Local Setup Tutorials

Use the tutorial that matches the machine:

- [macOS CPU venv setup](docs/tutorials/macos-cpu-venv.md)
- [Linux CPU venv setup](docs/tutorials/linux-cpu-venv.md)
- [Linux NVIDIA GPU venv setup](docs/tutorials/linux-nvidia-gpu-venv.md)
- [Docling ingestion format and pipeline guide](docs/docling-ingestion.md)
- [Extension playbooks](docs/extension-playbooks.md)

CPU tutorials install the base package directly and use [env-cpu](env-cpu).
The NVIDIA tutorial installs the default GPU requirements and uses
[env-cuda-gpu](env-cuda-gpu).

## API Usage

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?include_document=false&pipeline=standard" \
  -F "file=@/path/to/document.pdf"
```

The response includes the parser status and the output file paths.

For long-running GPU parses:

```bash
curl -X POST "http://127.0.0.1:8000/v1/ingest/file?async_mode=true&pipeline=vlm" \
  -F "file=@/path/to/document.pdf"
```

Check a persisted ingestion job:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}"
```

Download outputs:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/chunks"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/embedding"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/confidence"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/normalized"
curl "http://127.0.0.1:8000/v1/ingest/jobs/{job_id}/outputs/markdown"
```

## CLI Usage

```bash
python -m ingest_orquestator_server.cli parse /path/to/document.pdf \
  --parser docling \
  --pipeline standard \
  --profile rag_ready \
  --output-dir .data/outputs
```

Batch parse files or directories with Docling `convert_all`:

```bash
python -m ingest_orquestator_server.cli batch sample-inputs \
  --parser docling \
  --pipeline standard \
  --output-dir .data/outputs
```

Each parse creates a document-specific output directory containing:

- `raw_docling.json`
- `normalized.json`
- `document.md`
- `document.txt`
- `document.html`, when Docling can export HTML
- `chunks.json`
- `embedding_input.jsonl`
- `confidence.json`, when confidence output is enabled and Docling reports scores
- `manifest.json`

Benchmark configured pipelines:

```bash
python -m ingest_orquestator_server.cli benchmark /path/to/document.pdf --pipelines standard,vlm
```

Clean old local artifacts:

```bash
python -m ingest_orquestator_server.cli cleanup --older-than-days 30 --dry-run
python -m ingest_orquestator_server.cli cleanup --older-than-days 30 --delete
```

## Development Setup

For tests and linting, install the development extras into the same virtual environment:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
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
INGEST_PROFILE=rag_ready
INGEST_CHUNKING_ENABLED=true
INGEST_CHUNKING_STRATEGY=hybrid
INGEST_CHUNK_MAX_TOKENS=768
INGEST_CHUNK_SIZE_CHARS=1200
INGEST_CHUNK_OVERLAP_CHARS=150
INGEST_EMBEDDING_OUTPUT_ENABLED=true
INGEST_CONFIDENCE_OUTPUT_ENABLED=true
INGEST_CONFIDENCE_WARN_ONLY=true
INGEST_RETENTION_DAYS=30
INGEST_DOCLING_ACCELERATOR_DEVICE=auto
INGEST_DOCLING_NUM_THREADS=4
INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true
INGEST_DOCLING_ALLOWED_FORMATS=pdf,image,docx,pptx,html,md,xlsx,csv,json_docling,asciidoc,latex,vtt,xml_jats,xml_uspto,xml_xbrl
INGEST_DOCLING_PIPELINE=standard
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_VLM_RESPONSE_FORMAT=markdown
INGEST_DOCLING_VLM_RUNTIME=transformers
INGEST_DOCLING_XBRL_ENABLE_LOCAL_FETCH=false
INGEST_DOCLING_XBRL_ENABLE_REMOTE_FETCH=false
INGEST_DOCLING_PDF_LAYOUT_MODEL=docling-layout-heron-101
INGEST_DOCLING_PDF_OCR_ENGINE=suryaocr
INGEST_DOCLING_PDF_TABLE_STRUCTURE_BACKEND=tableformer
INGEST_DOCLING_PDF_TABLE_STRUCTURE_MODE=accurate
INGEST_DOCLING_PDF_TABLE_DO_CELL_MATCHING=true
INGEST_DOCLING_PDF_PICTURE_CLASSIFIER_PRESET=document_figure_classifier_v2
INGEST_DOCLING_PDF_PICTURE_DESCRIPTION_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_PDF_CODE_FORMULA_PRESET=codeformulav2
```

The standard pipeline is supported for every configured Docling format. Direct
VLM mode is supported for PDF and image inputs. The optional Granite
Vision table structure backend can be selected with:

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

1. Add vector database adapters.
2. Add RAG query APIs.
3. Add pre-rendering for Office/HTML VLM conversion if needed.
