# Architecture Diagram

This page describes the service architecture with Mermaid diagrams.

## System Context

```mermaid
flowchart LR
    User["Client / CLI user"] --> API["FastAPI API<br/>POST /v1/ingest/file"]
    User --> CLI["Typer CLI<br/>parse / batch / benchmark"]

    API --> App["Application services"]
    CLI --> App

    App --> Docling["Docling DocumentConverter"]
    App --> Storage["Local filesystem storage"]
    App --> Jobs["SQLite job repository"]
    App --> Queue["Local embedding queue<br/>v1.4 optional"]
    Queue --> Elastic["Official Elasticsearch Python client<br/>bulk or custom async"]

    Docling --> Models["Docling models<br/>Layout, OCR, tables, pictures, VLM"]
    Storage --> Outputs["Parse artifacts<br/>normalized, markdown, text, chunks, embedding JSONL, confidence"]
```

## Component View

```mermaid
flowchart TB
    subgraph Entrypoints["Entrypoints"]
        FastAPI["api/routes/ingestion.py"]
        CLIParse["cli/commands/parse_command.py"]
        CLIBatch["cli/commands/batch_command.py"]
        CLIBenchmark["cli/commands/benchmark_command.py"]
    end

    subgraph Application["Application Layer"]
        FileIngestion["FileIngestionService"]
        ParseService["DocumentParseService"]
        Chunking["DocumentChunkingService"]
        Embedding["EmbeddingRecordService"]
        OutputRetrieval["OutputRetrievalService"]
        JobQuery["JobQueryService"]
        EmbeddingQueue["EmbeddingQueueService"]
        EmbeddingDispatch["EmbeddingDispatchService"]
        Registry["ParserRegistry"]
    end

    subgraph Ports["Ports"]
        ParserPort["DocumentParser"]
        WriterPort["ParseOutputWriter"]
        UploadPort["UploadStorage"]
        JobRepoPort["IngestionJobRepository"]
        EmbeddingPort["EmbeddingDispatcher"]
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
        Profiles["Ingestion profiles"]
        EnvFiles[".env.example / env-cpu / env-cuda-gpu"]
    end

    FastAPI --> FileIngestion
    CLIParse --> ParseService
    CLIBatch --> ParseService
    CLIBenchmark --> ParseService

    FileIngestion --> UploadPort
    FileIngestion --> JobRepoPort
    FileIngestion --> ParseService
    FileIngestion --> EmbeddingDispatch
    FileIngestion --> JobQuery

    ParseService --> Registry
    ParseService --> Chunking
    ParseService --> Embedding
    ParseService --> WriterPort

    Registry --> ParserPort
    ParserPort --> DoclingParser
    WriterPort --> Writer
    UploadPort --> Uploads
    JobRepoPort --> SQLite
    EmbeddingPort --> ElasticDispatch
    EmbeddingDispatch --> EmbeddingQueue
    EmbeddingDispatch --> EmbeddingPort
    EmbeddingDispatch --> JobRepoPort

    DoclingParser --> ConverterFactory
    DoclingParser --> Normalizer
    ConverterFactory --> DoclingOptions

    Settings --> Profiles
    EnvFiles --> Settings
    Settings --> FileIngestion
    Settings --> ParseService
    Settings --> ConverterFactory
```

## Ingestion Sequence

```mermaid
sequenceDiagram
    participant Client as "Client or CLI"
    participant Route as "API route / CLI command"
    participant Ingestion as "FileIngestionService"
    participant Parser as "DoclingDocumentParser"
    participant Converter as "Docling DocumentConverter"
    participant Normalizer as "Docling normalizer"
    participant Chunker as "DocumentChunkingService"
    participant Writer as "LocalParseOutputWriter"
    participant Jobs as "SQLite job repository"
    participant EmbQueue as "Embedding queue / dispatcher"
    participant Elastic as "Official Elasticsearch Python client"

    Client->>Route: "Submit file and options"
    Route->>Ingestion: "ingest_upload or enqueue_upload"
    Ingestion->>Jobs: "Create queued/running job"
    Ingestion->>Parser: "parse(file, pipeline, profile)"
    Parser->>Converter: "convert or convert_all"
    Converter-->>Parser: "ConversionResult"
    Parser->>Normalizer: "Normalize Docling document"
    Normalizer-->>Parser: "ParsedDocument"
    Parser-->>Ingestion: "ParseOutput"
    Ingestion->>Chunker: "Build chunks with HybridChunker or configured strategy"
    Chunker-->>Ingestion: "DocumentChunk list"
    Ingestion->>Writer: "Write artifacts"
    Writer-->>Ingestion: "OutputFiles"
    Ingestion->>Jobs: "Persist completed/failed job"
    opt "INGEST_EMBEDDING_QUEUE_ENABLED=true"
        Ingestion->>EmbQueue: "Enqueue embedding_input.jsonl"
        EmbQueue->>Jobs: "status = embedding_queued"
        EmbQueue->>Elastic: "Submit chunks from up to 5 parsed docs"
        Elastic-->>EmbQueue: "bulk result or task id"
        EmbQueue->>Jobs: "status = sent_to_embedding_system"
    end
    Ingestion-->>Route: "IngestResponse"
    Route-->>Client: "Job, metadata, outputs, optional document/chunks"
```

## Embedding Handoff

```mermaid
flowchart LR
    Completed["Completed parse<br/>embedding_input.jsonl"] --> Queue["EmbeddingQueueService<br/>process-local"]
    Queue --> Bulk{"Up to<br/>max 5 parsed docs"}
    Bulk --> ChunkDocs["Flatten JSONL records<br/>1 chunk = 1 ES document"]
    ChunkDocs --> Submit["ElasticEmbeddingDispatcher<br/>official Python client"]
    Submit --> Task["Bulk marker or remote task id"]
    Task --> Poll["Poll custom async status"]
    Poll --> Done{"Task done?"}
    Done -->|No| Poll
    Done -->|Yes| CompletedState["embedding_completed"]
    Done -->|Failed| FailedState["embedding_failed"]
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
    VLMConverter --> Qwen["Qwen3 full-page VLM conversion"]
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
        CLIProcess["python -m ingest_orquestator_server.cli"]
        DataDir[".data directory"]
        ModelsCache["Model cache"]
    end

    subgraph OptionalGPU["NVIDIA GPU runtime"]
        CUDA["CUDA PyTorch"]
        Surya["SuryaOCR plugin"]
        Qwen["Qwen3-VL model"]
    end

    Venv --> APIProcess
    Venv --> CLIProcess
    APIProcess --> DataDir
    CLIProcess --> DataDir
    APIProcess --> ModelsCache
    CLIProcess --> ModelsCache
    APIProcess --> CUDA
    CLIProcess --> CUDA
    CUDA --> Surya
    CUDA --> Qwen
```
