# Open Source RAG Ingestion Project Context

This document summarizes the useful context from the NVIDIA RAG Blueprint and
NeMo Retriever exploration. It is intended as handoff context for starting a
new, simpler open-source RAG ingestion project.

## Goal

Build a project similar in spirit to NVIDIA RAG Enterprise / NVIDIA RAG
Blueprint, but less complex and based on open-source or free resources.

Initial scope:

- Focus first on the ingestion pipeline and its orchestration.
- Parse documents, extract structured content, normalize the output, and prepare
  it for later chunking, embedding, and retrieval.
- Do not start with the full RAG query stack.
- Prefer local/open-source components where possible.

## NVIDIA RAG Blueprint Context

Repository path used during exploration:

```text
/Users/aromlo1/Documents/rag
```

Relevant project structure:

```text
src/nvidia_rag/
├── rag_server/        # RAG query/response FastAPI server
├── ingestor_server/   # Document ingestion FastAPI server
└── utils/             # Shared utilities
frontend/              # React + TypeScript UI
deploy/compose/        # Docker Compose deployment
deploy/helm/           # Helm deployment
docs/                  # Documentation
tests/                 # Unit and integration tests
```

The important ingestion files in the NVIDIA Blueprint are:

```text
src/nvidia_rag/ingestor_server/
src/nvidia_rag/ingestor_server/nvingest.py
src/nvidia_rag/utils/configuration.py
src/nvidia_rag/utils/vdb/vdb_ingest_base.py
deploy/compose/
pyproject.toml
```

Key findings:

- The Blueprint ingestion API is a FastAPI service.
- It delegates document parsing/extraction to NV-Ingest.
- It supports downstream vector database ingestion.
- The repo does not vendor the full NV-Ingest implementation.
- It depends on NVIDIA packages:

```text
nv-ingest-api==26.1.2
nv-ingest-client==26.1.2
```

- Docker Compose starts an external NVIDIA runtime image:

```text
nvcr.io/nvidia/nemo-microservices/nv-ingest:26.1.2
```

So, in the Blueprint repo, NV-Ingest is mainly consumed as an external service
and client dependency, not implemented directly inside the repo.

## NV-Ingest And NeMo Retriever Findings

The NeMo Retriever repository was cloned here:

```text
/Users/aromlo1/Documents/rag/src/NeMo-Retriever
```

Important conclusion:

```text
NV-Ingest is the older/product/service name.
NeMo Retriever extraction is the newer public library direction.
```

The cloned NeMo Retriever repo contains both legacy NV-Ingest references and the
newer `nemo_retriever` Python package.

Legacy NV-Ingest references found:

```text
config/default_pipeline.yaml
docker-compose.yaml
examples/launch_libmode_and_run_ingestor.py
```

Examples import older client APIs such as:

```python
from nv_ingest_client.client import Ingestor, NvIngestClient
```

However, the actual legacy `src/nv_ingest`, `api`, and `client` source trees
were not present in the clone that was inspected.

Newer NeMo Retriever package:

```text
nemo_retriever/src/nemo_retriever/
```

Important files:

```text
nemo_retriever/src/nemo_retriever/ingestor.py
nemo_retriever/src/nemo_retriever/graph_ingestor.py
nemo_retriever/src/nemo_retriever/graph/ingestor_runtime.py
nemo_retriever/src/nemo_retriever/params/models.py
nemo_retriever/src/nemo_retriever/vdb/operators.py
nemo_retriever/src/nemo_retriever/service_ingestor.py
```

Public API pattern:

```python
from nemo_retriever import create_ingestor

result = (
    create_ingestor(run_mode="inprocess")
    .files(["document.pdf"])
    .extract(...)
    .ingest()
)
```

Main fluent pipeline stages:

```text
files()
-> extract()
-> caption()
-> embed()
-> vdb_upload()
-> ingest()
```

Supported run modes:

```text
inprocess  # local Python graph execution
batch      # batch execution
service    # service/API mode
```

Service mode exposes FastAPI-style job endpoints such as:

```text
/v1/ingest/job
/document
/page
/whole
```

Default vector database support in the library includes LanceDB.

## NeMo Retriever Extraction Pipeline Shape

The NeMo Retriever extraction graph can perform stages similar to NV-Ingest:

- File input.
- PDF splitting.
- PDF text extraction.
- OCR.
- Page element detection.
- Table structure extraction.
- Graphic element extraction.
- Optional Nemotron Parse mode.
- Optional captioning.
- Optional embedding.
- Optional vector database upload.
- Optional webhook/status handling.

For our simplified project, the important part is only:

```text
file input
-> document parsing
-> normalized document structure
-> optional markdown/json output
```

No database, embeddings, or RAG are required for the first experiment.

## Local Script Created For NeMo Retriever Testing

A local helper script was created in the NVIDIA Blueprint repo:

```text
/Users/aromlo1/Documents/rag/scripts/parse_pdf_nemo_retriever.py
```

Purpose:

- Parse a PDF with NeMo Retriever.
- Do not ingest into a vector database.
- Do not run RAG.
- Save raw JSON, Markdown, and per-page JSON outputs.

Important arguments:

```text
pdf
--output-dir
--run-mode {inprocess,batch}
--method {pdfium,pdfium_hybrid,ocr,nemotron_parse}
--text-only
--extract-images
--use-table-structure
--use-graphic-elements
--dpi
--ocr-version
--ocr-lang
--allow-no-gpu
```

Basic text-only command used on the A100 server:

```bash
CUDA_VISIBLE_DEVICES=0 python parse_nemp.py DEVELOP_TAiTAN_LITE_V1.pdf \
  --text-only \
  --output-dir ./nemo_parse_output
```

Advanced extraction command used after GPU driver issues were fixed:

```bash
CUDA_VISIBLE_DEVICES=0 python parse_nemp.py DEVELOP_TAiTAN_LITE_V1.pdf \
  --run-mode inprocess \
  --method pdfium \
  --use-table-structure \
  --use-graphic-elements \
  --extract-images \
  --output-dir ./nemo_parse_output_advanced
```

Successful advanced output included 13 rows, one per page, with columns such as:

```text
path
page_number
source_id
text
page_image
images
tables
charts
infographics
metadata
page_elements_v3
page_elements_v3_num_detections
page_elements_v3_counts_by_label
table_structure_v1
table_structure_ocr_v1
table_structure_v1_num_detections
table_structure_v1_counts_by_label
graphic_elements_ocr_v1
graphic_elements_v1_num_detections
graphic_elements_v1_counts_by_label
ocr
ocr_v1_num_detections
ocr_v1_counts_by_label
```

The tested PDF was mostly text, so advanced extraction worked but did not
necessarily produce many tables, charts, images, or infographics.

## A100 / CUDA Note

The first remote attempt failed because the installed PyTorch wheel targeted a
newer CUDA runtime than the server driver supported.

Observed server context:

```text
Driver: 535.309.01
CUDA shown by nvidia-smi: 12.2
GPU: A100
```

Problem:

```text
PyTorch CUDA 13 wheel was installed.
Driver 535 / CUDA 12.2 could not load it.
```

Resolution:

- Upgrade the NVIDIA driver, or
- Install a PyTorch build compatible with the server driver/CUDA runtime.

After the driver issue was resolved, NeMo Retriever advanced extraction ran
successfully.

## Open Source Equivalents To NV-Ingest Pipeline Stages

There is no single open-source drop-in replacement that fully matches:

```text
NV-Ingest + NVIDIA NIMs + orchestration + GPU services + Blueprint integration
```

But the same pipeline can be rebuilt from open-source components.

Recommended stage mapping:

| Stage | Open-source options |
| --- | --- |
| File upload/API | FastAPI, Starlette |
| File type detection | python-magic, filetype, Unstructured |
| PDF text extraction | Docling, PyMuPDF, PyMuPDF4LLM, pypdfium2 |
| OCR | Docling OCR, PaddleOCR, Tesseract, EasyOCR, Surya |
| Layout detection | Docling, MinerU, Marker, PaddleOCR PP-Structure, Surya |
| Tables | Docling TableFormer, PaddleOCR PP-Structure, MinerU, Marker |
| Formulas | MinerU, Marker |
| Images | PyMuPDF, Docling, MinerU, Marker |
| Captions | Qwen-VL, InternVL, LLaVA, Florence-style models |
| Chunking | LangChain, LlamaIndex, Unstructured, custom splitter |
| Embeddings | sentence-transformers, BGE, E5, Nomic Embed, Instructor |
| Vector DB | Qdrant, Chroma, LanceDB, Milvus, pgvector |
| Queue/orchestration | Celery, Dramatiq, RQ, Prefect, Dagster, FastAPI background tasks |
| Job state | SQLite, PostgreSQL, Redis |
| Object storage | Local filesystem, MinIO, S3-compatible storage |

## Docling Vs MinerU Recommendation

For the first version of the new project, start with:

```text
Docling as the default parser.
MinerU as an optional advanced parser later.
```

Why Docling first:

- Easier to embed directly as a Python library.
- Good fit for a smaller MVP.
- Supports useful document formats beyond PDF.
- Produces practical Markdown/JSON-style outputs for RAG ingestion.
- MIT licensed.
- Lower operational complexity than a GPU-heavy parser service.

Where MinerU is stronger:

- Difficult scientific or academic PDFs.
- Formula extraction to LaTeX.
- Complex tables.
- Scanned documents.
- Multilingual OCR.
- Cross-page table handling.
- More advanced parser service patterns.

Important caveat:

- Docling is a better default engineering choice for the first project.
- MinerU may produce better results on some difficult PDFs, but it is heavier
  and its license has extra conditions compared with plain MIT.

External references:

```text
https://github.com/docling-project/docling
https://github.com/opendatalab/MinerU
https://github.com/datalab-to/marker
https://github.com/Unstructured-IO/unstructured
https://github.com/pymupdf/pymupdf4llm
```

## Proposed MVP Architecture

Start with a small but extensible ingestion service:

```text
FastAPI ingestion API
-> file storage
-> job table
-> parser interface
-> Docling parser implementation
-> normalized document JSON
-> chunking
-> embeddings
-> vector database
```

Initial parser interface:

```python
class DocumentParser:
    def parse(self, file_path: str) -> ParsedDocument:
        ...
```

Initial implementations:

```text
DoclingParser      # default
MinerUParser       # optional future advanced backend
PyMuPDFParser      # optional lightweight fallback
```

Suggested first normalized model:

```text
ParsedDocument
├── document_id
├── source_path
├── mime_type
├── title
├── pages[]
├── elements[]
└── metadata
```

Suggested element model:

```text
DocumentElement
├── element_id
├── page_number
├── type              # text, title, table, image, formula, caption, list
├── text
├── markdown
├── html
├── bbox
├── confidence
└── metadata
```

Suggested chunk model:

```text
DocumentChunk
├── chunk_id
├── document_id
├── page_start
├── page_end
├── text
├── metadata
└── embedding
```

## Recommended First Milestones

Milestone 1: Parser-only CLI

- Input: one PDF file.
- Parser: Docling.
- Output: raw JSON, normalized JSON, Markdown.
- No API, no DB, no embeddings.

Milestone 2: Ingestion API

- FastAPI endpoint to upload a file.
- Store file locally.
- Create an ingestion job.
- Run parser in background.
- Persist job status and parsed output.

Milestone 3: Chunking

- Convert normalized elements into chunks.
- Keep page numbers and source metadata.
- Write chunks to JSON first.

Milestone 4: Embeddings and vector DB

- Use `sentence-transformers`.
- Start with Qdrant, LanceDB, Chroma, or pgvector.
- Keep the vector DB behind an adapter interface.

Milestone 5: Optional advanced parser

- Add MinerU as a second parser backend.
- Route difficult PDFs to MinerU based on configuration or file profile.

## Practical Default Stack

Recommended first stack:

```text
Python 3.11+
FastAPI
Docling
Pydantic
SQLite or PostgreSQL
Local filesystem storage
sentence-transformers
Qdrant or pgvector
Docker Compose
```

Keep the first implementation boring and inspectable:

- One API service.
- One worker process or background task.
- One parser backend.
- One normalized output format.
- JSON files for debugging.
- Add the vector database after parsing is trustworthy.

## Design Principle

Do not copy NVIDIA's operational complexity at the beginning.

Copy the pipeline shape:

```text
file
-> parse
-> normalize
-> chunk
-> embed
-> index
-> retrieve
```

But replace the implementation with smaller open-source components and clean
interfaces.

