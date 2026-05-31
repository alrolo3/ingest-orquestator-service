# Architecture Diagram

This page describes the service architecture with Mermaid diagrams.

## System Context

```mermaid
flowchart LR
    User["API client"] --> API["FastAPI API<br/>POST /v1/ingest/file"]

    API --> App["Application services"]

    App --> Jobs["SQLite job repository"]
    App --> ParserWorkers["Parser worker pool"]
    ParserWorkers --> Docling["Docling DocumentConverter"]
    ParserWorkers --> Queue["Mandatory full-document dispatch queue"]
    Queue --> Dispatcher["Dispatcher service thread"]
    Dispatcher --> Storage["Local filesystem storage"]
    Dispatcher --> Elastic["Official Elasticsearch Python client<br/>helpers.bulk"]

    Docling --> Models["Docling models<br/>Layout, OCR, tables, pictures, VLM"]
    Storage --> Outputs["Parse artifacts<br/>normalized, markdown, text, chunks, embedding JSONL, confidence"]
```

## Component View

```mermaid
flowchart TB
    subgraph Entrypoints["Entrypoints"]
        FastAPI["api/routes/ingestion.py"]
    end

    subgraph Application["Application Layer"]
        FileIngestion["FileIngestionService"]
        ParseService["DocumentParseService"]
        Chunking["DocumentChunkingService"]
        Embedding["EmbeddingRecordService"]
        OutputRetrieval["OutputRetrievalService"]
        JobQuery["JobQueryService"]
        ParserWorkers["ParserWorkerService"]
        DispatchQueue["EmbeddingQueueService<br/>(full-document dispatch queue)"]
        DispatchService["EmbeddingDispatchService<br/>(dispatcher coordinator)"]
        Registry["ParserRegistry"]
    end

    subgraph Ports["Ports"]
        ParserPort["DocumentParser"]
        WriterPort["ParseOutputWriter"]
        UploadPort["UploadStorage"]
        JobRepoPort["IngestionJobRepository"]
        DispatchPort["EmbeddingDispatcher<br/>(Elastic sink port)"]
    end

    subgraph Infrastructure["Infrastructure Adapters"]
        DoclingParser["DoclingDocumentParser"]
        ConverterFactory["DoclingConverterFactory"]
        DoclingOptions["Docling options builders"]
        Normalizer["DoclingDocumentNormalizer"]
        Writer["LocalParseOutputWriter"]
        Uploads["LocalUploadStorage"]
        SQLite["SqliteIngestionJobRepository"]
        ElasticDispatch["ElasticEmbeddingDispatcher"]
    end

    subgraph Config["Configuration"]
        Settings["Settings"]
        EnvFiles[".env.example / env-cpu / env-cuda-gpu"]
    end

    FastAPI --> FileIngestion

    FileIngestion --> UploadPort
    FileIngestion --> JobRepoPort
    FileIngestion --> ParserWorkers
    FileIngestion --> JobQuery

    ParserWorkers --> ParseService
    ParserWorkers --> DispatchService
    ParseService --> Registry
    ParseService --> Chunking
    ParseService --> Embedding
    ParseService --> WriterPort

    Registry --> ParserPort
    ParserPort --> DoclingParser
    WriterPort --> Writer
    UploadPort --> Uploads
    JobRepoPort --> SQLite
    DispatchPort --> ElasticDispatch
    DispatchService --> DispatchQueue
    DispatchService --> DispatchPort
    DispatchService --> WriterPort
    DispatchService --> JobRepoPort

    DoclingParser --> ConverterFactory
    DoclingParser --> Normalizer
    ConverterFactory --> DoclingOptions

    EnvFiles --> Settings
    Settings --> FileIngestion
    Settings --> ParserWorkers
    Settings --> ParseService
    Settings --> ConverterFactory
```

## Ingestion Sequence

```mermaid
sequenceDiagram
    participant Client as "API client"
    participant Route as "API route"
    participant Ingestion as "FileIngestionService"
    participant Worker as "ParserWorkerService"
    participant Parser as "DoclingDocumentParser"
    participant Converter as "Docling DocumentConverter"
    participant Normalizer as "Docling normalizer"
    participant Chunker as "DocumentChunkingService"
    participant Jobs as "SQLite job repository"
    participant Queue as "Full-document dispatch queue"
    participant Dispatch as "Dispatcher service thread"
    participant Writer as "LocalParseOutputWriter"
    participant Elastic as "Official Elasticsearch Python client"

    Client->>Route: "Submit file and options"
    Route->>Ingestion: "ingest_upload"
    Ingestion->>Jobs: "Create parser_queued job"
    Ingestion->>Worker: "submit_job(job_id)"
    Ingestion-->>Route: "IngestResponse with status URL"
    Route-->>Client: "Job metadata"
    Worker->>Jobs: "status = parsing"
    Worker->>Parser: "parse(file, pipeline)"
    Parser->>Converter: "convert"
    Converter-->>Parser: "ConversionResult"
    Parser->>Normalizer: "Normalize Docling document"
    Normalizer-->>Parser: "ParsedDocument"
    Parser-->>Worker: "ParseOutput"
    Worker->>Chunker: "Build configured RAG chunks"
    Chunker-->>Worker: "DocumentChunk list"
    Worker->>Queue: "Enqueue full parsed document"
    Queue->>Jobs: "status = dispatch_queued"
    Dispatch->>Queue: "Drain up to INGEST_DISPATCH_MAX_BULK_SIZE documents"
    Dispatch->>Jobs: "status = dispatching"
    opt "INGEST_DISPATCH_SINK_MODE includes local"
        Dispatch->>Writer: "Write local artifacts"
        Writer-->>Dispatch: "OutputFiles"
        Dispatch->>Jobs: "status = stored_local"
    end
    opt "INGEST_DISPATCH_SINK_MODE includes elastic"
        Dispatch->>Elastic: "Bulk one item per chunk"
        Elastic-->>Dispatch: "bulk success or item errors"
    end
    Dispatch->>Jobs: "status = completed or failed"
```

## Dispatch Handoff

```mermaid
flowchart LR
    Parsed["Parsed full document<br/>ParseOutput + chunks + embedding records"] --> Queue["Process-local dispatch queue<br/>bounded depth and payload size"]
    Queue --> Bulk{"Up to<br/>INGEST_DISPATCH_MAX_BULK_SIZE docs"}
    Bulk --> Store["Optional local sink<br/>normalized, markdown, chunks, confidence"]
    Bulk --> ChunkDocs["Dispatcher creates<br/>1 chunk = 1 ES document"]
    ChunkDocs --> Submit["ElasticEmbeddingDispatcher<br/>official Python client"]
    Submit --> BulkCall["helpers.bulk"]
    BulkCall --> Done{"Bulk succeeded?"}
    Done -->|Yes| CompletedState["completed"]
    Done -->|No| FailedState["retry or failed"]
```

## Docling Pipeline Routing

```mermaid
flowchart TD
    Input["Input file"] --> Detect["detect_input_format"]
    Detect --> Validate["validate_allowed_format"]
    Validate --> Resolve["resolve_pipeline_mode"]

    Resolve --> Standard{"pipeline = standard?"}
    Standard -->|Yes| StandardConverter["DocumentConverter<br/>standard format options"]
    Standard -->|No| VLMCheck{"PDF or image?"}
    VLMCheck -->|Yes| VLMConverter["DocumentConverter<br/>VlmPipeline"]
    VLMCheck -->|No| Error["UnsupportedPipelineError"]

    StandardConverter --> PdfImage["PDF / image<br/>PdfPipelineOptions"]
    StandardConverter --> Simple["DOCX, PPTX, HTML, MD, CSV, XLSX, XML, VTT, LaTeX<br/>Docling defaults or backend options"]
    StandardConverter --> XBRL["XBRL<br/>XBRLBackendOptions"]

    PdfImage --> Stages["Layout, OCR, table structure,<br/>picture classification/description,<br/>code/formula enrichment"]
    VLMConverter --> VLMRuntime["Local Transformers<br/>or RemoteLLM endpoint"]
    XBRL --> Taxonomy["Local/remote taxonomy fetch controls"]
```

## Output Model

```mermaid
flowchart LR
    ParseOutput["ParseOutput"] --> Normalized["ParsedDocument<br/>normalized.json"]
    ParseOutput --> Raw["raw_docling.json"]
    ParseOutput --> Markdown["document.md"]
    ParseOutput --> Text["document.txt"]
    ParseOutput --> Html["document.html"]
    ParseOutput --> Confidence["confidence.json"]

    Normalized --> Chunks["chunks.json"]
    Chunks --> Embedding["embedding_input.jsonl"]
    Confidence --> Manifest["manifest.json"]
    Embedding --> Manifest
    Raw --> Manifest
    Markdown --> Manifest
    Text --> Manifest
    Html --> Manifest
```

## Deployment View

```mermaid
flowchart TB
    subgraph Host["Local host or GPU server"]
        Venv["Python venv"]
        APIProcess["uvicorn process"]
        DataDir[".data directory"]
        ModelsCache["Model cache"]
    end

    subgraph OptionalGPU["NVIDIA GPU runtime"]
        CUDA["CUDA PyTorch"]
        Surya["SuryaOCR plugin"]
        Qwen["Local Qwen3-VL model"]
        RemoteLLM["External RemoteLLM server<br/>OpenAI-compatible endpoint"]
    end

    Venv --> APIProcess
    APIProcess --> DataDir
    APIProcess --> ModelsCache
    APIProcess --> CUDA
    APIProcess --> RemoteLLM
    CUDA --> Surya
    CUDA --> Qwen
```
