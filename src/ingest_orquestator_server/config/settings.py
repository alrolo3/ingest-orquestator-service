import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingest_orquestator_server.config.config_groups import (
    ChunkingConfig,
    ConfidenceConfig,
    DispatchConfig,
    DoclingCommonConfig,
    DoclingOcrConfig,
    DoclingVlmConfig,
    DoclingXbrlConfig,
    EmbeddingQueueConfig,
    ProgressConfig,
    ServiceConfig,
    StorageConfig,
    UploadConfig,
)
from ingest_orquestator_server.config.docling_defaults import (
    DOCLING_CODE_FORMULA_PRESET,
    DOCLING_LAYOUT_MODEL,
    DOCLING_OCR_ENGINE,
    DOCLING_OCR_LANGUAGES,
    DOCLING_PICTURE_CLASSIFIER_PRESET,
    DOCLING_PICTURE_DESCRIPTION_MODEL,
    DOCLING_PICTURE_DESCRIPTION_PROMPT,
    DOCLING_TABLE_STRUCTURE_BACKEND,
    DOCLING_TABLE_STRUCTURE_BACKEND_GRANITE_VISION,
    DOCLING_TABLE_STRUCTURE_BACKEND_TABLEFORMER,
    DOCLING_TABLE_STRUCTURE_MODE,
    DOCLING_TABLE_STRUCTURE_VLM_MODEL,
)


class Settings(BaseSettings):
    service_name: str = "ingest-orquestator-server"
    storage_dir: Path = Path(".data")
    max_upload_size_mb: int = Field(default=100, ge=1)
    allowed_upload_extensions: list[str] = Field(
        default_factory=lambda: [
            ".adoc",
            ".asciidoc",
            ".bmp",
            ".csv",
            ".htm",
            ".html",
            ".jats",
            ".jpeg",
            ".jpg",
            ".json",
            ".latex",
            ".pdf",
            ".png",
            ".md",
            ".markdown",
            ".nxml",
            ".pptx",
            ".tex",
            ".tif",
            ".tiff",
            ".txt",
            ".uspto",
            ".vtt",
            ".webp",
            ".docx",
            ".xlsx",
            ".xbrl",
        ]
    )
    chunk_size_chars: int = Field(default=1200, ge=100)
    chunk_overlap_chars: int = Field(default=150, ge=0)
    chunking_enabled: bool = True
    chunking_strategy: str = "hybrid"
    chunk_max_tokens: int = Field(default=768, ge=32)
    chunk_tokenizer_model: str | None = None
    chunk_merge_peers: bool = True
    chunk_repeat_table_header: bool = True
    chunk_omit_header_on_overflow: bool = False
    chunk_omit_prefix_on_overflow: bool = False
    confidence_output_enabled: bool = True
    confidence_min_document_score: float | None = Field(default=None, ge=0, le=1)
    confidence_warn_only: bool = True
    progress_log_interval_seconds: float = Field(default=30.0, ge=0)
    progress_page_interval: int = Field(default=1, ge=1)
    progress_history_limit: int = Field(default=50, ge=1)
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    retention_days: int = Field(default=30, ge=1)
    docling_accelerator_device: str = Field(
        default="auto",
        description="Docling accelerator device: auto, cpu, cuda, cuda:N, mps, or xpu.",
    )
    docling_num_threads: int = Field(default=4, ge=1)
    docling_cuda_use_flash_attention2: bool = False
    docling_allow_external_plugins: bool = Field(
        default=True,
        description="Allow Docling external plugins. Required for the SuryaOCR plugin.",
    )
    docling_engine_cache_enabled: bool = True
    docling_engine_warmup_enabled: bool = False
    docling_engine_warmup_formats: list[str] = Field(default_factory=lambda: ["pdf"])
    docling_gpu_engine_concurrency: int = Field(default=1, ge=1)
    docling_gpu_batch_max_documents: int = Field(default=5, ge=1, le=32)
    docling_gpu_batch_wait_ms: int = Field(default=250, ge=0)
    docling_engine_idle_ttl_seconds: int = Field(default=0, ge=0)
    docling_perf_page_batch_size: int | None = Field(default=None, ge=1)
    docling_allowed_formats: list[str] = Field(
        default_factory=lambda: [
            "pdf",
            "image",
            "docx",
            "pptx",
            "html",
            "md",
            "xlsx",
            "csv",
            "json_docling",
            "asciidoc",
            "latex",
            "vtt",
            "xml_jats",
            "xml_uspto",
            "xml_xbrl",
        ]
    )
    docling_pipeline: str = "standard"
    docling_pdf_do_ocr: bool = True
    docling_pdf_ocr_engine: str = DOCLING_OCR_ENGINE
    docling_pdf_ocr_languages: list[str] = Field(
        default_factory=lambda: list(DOCLING_OCR_LANGUAGES)
    )
    docling_pdf_ocr_use_gpu: bool | None = None
    docling_pdf_do_table_structure: bool = True
    docling_pdf_layout_model: str = DOCLING_LAYOUT_MODEL
    docling_pdf_table_structure_backend: str = DOCLING_TABLE_STRUCTURE_BACKEND
    docling_pdf_table_structure_mode: str = DOCLING_TABLE_STRUCTURE_MODE
    docling_pdf_table_do_cell_matching: bool = True
    docling_pdf_table_structure_vlm_model: str = DOCLING_TABLE_STRUCTURE_VLM_MODEL
    docling_pdf_do_picture_classification: bool = True
    docling_pdf_picture_classifier_preset: str = DOCLING_PICTURE_CLASSIFIER_PRESET
    docling_pdf_do_picture_description: bool = True
    docling_pdf_picture_description_model: str = DOCLING_PICTURE_DESCRIPTION_MODEL
    docling_pdf_picture_description_runtime: str = "transformers"
    docling_pdf_picture_description_prompt: str = DOCLING_PICTURE_DESCRIPTION_PROMPT
    docling_pdf_picture_description_max_new_tokens: int = Field(default=1024, ge=1)
    docling_pdf_do_code_enrichment: bool = True
    docling_pdf_do_formula_enrichment: bool = True
    docling_pdf_code_formula_preset: str = DOCLING_CODE_FORMULA_PRESET
    docling_pdf_ocr_batch_size: int = Field(default=4, ge=1)
    docling_pdf_layout_batch_size: int = Field(default=4, ge=1)
    docling_pdf_table_batch_size: int = Field(default=4, ge=1)
    docling_pdf_queue_max_size: int = Field(default=100, ge=1)
    docling_vlm_model: str = DOCLING_PICTURE_DESCRIPTION_MODEL
    docling_vlm_prompt: str = "Convert this page to markdown."
    docling_vlm_response_format: str = "markdown"
    docling_vlm_runtime: str = "transformers"
    docling_vlm_scale: float = Field(default=2.0, gt=0)
    docling_vlm_torch_dtype: str | None = "bfloat16"
    docling_vlm_load_in_8bit: bool = False
    docling_vlm_max_new_tokens: int = Field(default=4096, ge=1)
    docling_vlm_trust_remote_code: bool = False
    docling_remote_llm_url: str = "http://localhost:8000/v1/chat/completions"
    docling_remote_llm_model: str | None = None
    docling_remote_llm_api_key: str | None = None
    docling_remote_llm_api_key_header: str = "Authorization"
    docling_remote_llm_api_key_scheme: str = "Bearer"
    docling_remote_llm_timeout_seconds: float = Field(default=90.0, gt=0)
    docling_remote_llm_concurrency: int = Field(default=1, ge=1)
    docling_remote_llm_page_batch_size: int | None = Field(default=None, ge=1)
    docling_remote_llm_max_tokens: int = Field(default=4096, ge=1)
    docling_remote_llm_temperature: float = Field(default=0.0, ge=0)
    docling_remote_llm_provider: str = "openai_compatible"
    docling_remote_llm_health_check_enabled: bool = False
    docling_remote_llm_health_check_timeout_seconds: float = Field(default=5.0, gt=0)
    docling_xbrl_enable_local_fetch: bool = False
    docling_xbrl_enable_remote_fetch: bool = False
    docling_xbrl_taxonomy_path: Path | None = None
    embedding_output_enabled: bool = True
    queue_backend: str = "local"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672//"
    dramatiq_parser_queue_name: str = "ingest_parser_jobs"
    dramatiq_dispatch_queue_name: str = "ingest_dispatch_jobs"
    parser_worker_count: int = Field(default=2, ge=1)
    dispatch_worker_count: int = Field(default=2, ge=1)
    dispatch_queue_max_size: int = Field(default=100, ge=1)
    dispatch_queue_max_payload_bytes: int | None = Field(default=None, ge=1)
    dispatch_max_bulk_size: int = Field(default=5, ge=1, le=5)
    dispatch_idle_interval_seconds: float = Field(default=0.5, gt=0)
    dispatch_sink_mode: str = "local"
    dispatch_max_retries: int = Field(default=3, ge=0)
    embedding_elastic_url: str | None = None
    embedding_elastic_username: str | None = None
    embedding_elastic_password: str | None = None
    embedding_elastic_index: str = "ingest-embedding-input"
    embedding_elastic_mapping_version: str = "v1"
    embedding_elastic_pipeline: str | None = None
    embedding_elastic_verify_certs: bool = True
    embedding_elastic_request_timeout_seconds: float = Field(default=30.0, gt=0)
    embedding_elastic_max_retries: int = Field(default=3, ge=0)

    model_config = SettingsConfigDict(
        env_prefix="INGEST_",
        env_file=".env",
        extra="ignore",
        enable_decoding=False,
    )

    @field_validator("docling_accelerator_device")
    @classmethod
    def validate_docling_accelerator_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"auto", "cpu", "cuda", "mps", "xpu"}:
            return normalized
        if re.fullmatch(r"cuda:\d+", normalized):
            return normalized
        raise ValueError("must be one of auto, cpu, cuda, cuda:N, mps, or xpu")

    @field_validator("docling_pdf_ocr_engine")
    @classmethod
    def normalize_docling_pdf_ocr_engine(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("docling_pipeline")
    @classmethod
    def validate_docling_pipeline(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"standard", "vlm", "auto"}:
            return normalized
        raise ValueError("must be one of standard, vlm, or auto")

    @field_validator("chunking_strategy")
    @classmethod
    def validate_chunking_strategy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"hybrid", "line_based", "legacy_char"}:
            return normalized
        raise ValueError("must be one of hybrid, line_based, or legacy_char")

    @field_validator("docling_allowed_formats", mode="before")
    @classmethod
    def parse_docling_allowed_formats(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("docling_allowed_formats")
    @classmethod
    def normalize_docling_allowed_formats(cls, value: list[str]) -> list[str]:
        valid_formats = {
            "docx",
            "pptx",
            "html",
            "image",
            "pdf",
            "asciidoc",
            "md",
            "csv",
            "xlsx",
            "xml_uspto",
            "xml_jats",
            "xml_xbrl",
            "mets_gbs",
            "json_docling",
            "audio",
            "vtt",
            "latex",
        }
        normalized = sorted({item.strip().lower() for item in value if item.strip()})
        unknown = sorted(set(normalized) - valid_formats)
        if unknown:
            raise ValueError(f"unknown Docling input format(s): {', '.join(unknown)}")
        return normalized

    @field_validator("docling_engine_warmup_formats", mode="before")
    @classmethod
    def parse_docling_engine_warmup_formats(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("docling_engine_warmup_formats")
    @classmethod
    def normalize_docling_engine_warmup_formats(cls, value: list[str]) -> list[str]:
        valid_formats = {
            "pdf",
            "image",
            "docx",
            "pptx",
            "html",
            "md",
            "xlsx",
            "csv",
            "json_docling",
            "asciidoc",
            "latex",
            "vtt",
            "xml_jats",
            "xml_uspto",
            "xml_xbrl",
            "mets_gbs",
            "audio",
        }
        normalized = sorted({item.strip().lower() for item in value if item.strip()})
        unknown = sorted(set(normalized) - valid_formats)
        if unknown:
            raise ValueError(f"unknown Docling warmup format(s): {', '.join(unknown)}")
        return normalized

    @field_validator("docling_pdf_ocr_languages", mode="before")
    @classmethod
    def parse_docling_pdf_ocr_languages(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("docling_pdf_layout_model")
    @classmethod
    def normalize_docling_pdf_layout_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("docling_pdf_table_structure_backend")
    @classmethod
    def validate_docling_pdf_table_structure_backend(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if normalized in {
            DOCLING_TABLE_STRUCTURE_BACKEND_TABLEFORMER,
            DOCLING_TABLE_STRUCTURE_BACKEND_GRANITE_VISION,
        }:
            return normalized
        raise ValueError("must be one of tableformer or granite_vision")

    @field_validator("docling_pdf_table_structure_mode")
    @classmethod
    def validate_docling_pdf_table_structure_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"fast", "accurate"}:
            return normalized
        raise ValueError("must be one of fast or accurate")

    @field_validator("docling_vlm_response_format")
    @classmethod
    def validate_docling_vlm_response_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {
            "doctags",
            "doclang",
            "markdown",
            "deepseekocr_markdown",
            "html",
            "otsl",
            "plaintext",
        }:
            return normalized
        raise ValueError("must be a valid Docling VLM response format")

    @field_validator("docling_vlm_runtime")
    @classmethod
    def validate_docling_vlm_runtime(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if normalized in {"remote", "remote_llm", "api"}:
            return "remote_llm"
        if normalized in {"auto", "auto_inline", "transformers"}:
            return normalized
        raise ValueError("must be one of auto, auto_inline, transformers, or remote_llm")

    @field_validator("docling_pdf_picture_description_runtime")
    @classmethod
    def validate_docling_pdf_picture_description_runtime(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if normalized in {"remote", "remote_llm", "api"}:
            return "remote_llm"
        if normalized in {"auto", "auto_inline", "transformers"}:
            return normalized
        raise ValueError("must be one of auto, auto_inline, transformers, or remote_llm")

    @field_validator("docling_remote_llm_url")
    @classmethod
    def validate_docling_remote_llm_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("must be an HTTP(S) URL")
        return cleaned

    @field_validator("docling_remote_llm_provider")
    @classmethod
    def validate_docling_remote_llm_provider(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if normalized in {"openai_compatible", "openai"}:
            return "openai_compatible"
        raise ValueError("must be openai_compatible")

    @field_validator("allowed_upload_extensions", mode="before")
    @classmethod
    def parse_allowed_upload_extensions(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_allow_origins")
    @classmethod
    def normalize_cors_allow_origins(cls, value: list[str]) -> list[str]:
        return sorted({origin.strip().rstrip("/") for origin in value if origin.strip()})

    @field_validator("allowed_upload_extensions")
    @classmethod
    def normalize_allowed_upload_extensions(cls, value: list[str]) -> list[str]:
        normalized = []
        for extension in value:
            cleaned = extension.strip().lower()
            if not cleaned:
                continue
            normalized.append(cleaned if cleaned.startswith(".") else f".{cleaned}")
        return sorted(set(normalized))

    @field_validator(
        "embedding_elastic_url",
        "embedding_elastic_username",
        "embedding_elastic_password",
        "embedding_elastic_pipeline",
        "docling_remote_llm_model",
        "docling_remote_llm_api_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("embedding_elastic_index")
    @classmethod
    def normalize_embedding_elastic_index(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("embedding_elastic_mapping_version")
    @classmethod
    def validate_embedding_elastic_mapping_version(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if normalized in {"v1", "dense_vector", "dense_vector_v1"}:
            return "v1"
        if normalized in {"v2", "semantic_text", "semantic_text_v2"}:
            return "v2"
        raise ValueError("must be one of v1, dense_vector_v1, v2, or semantic_text_v2")

    @field_validator("dispatch_sink_mode")
    @classmethod
    def validate_dispatch_sink_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"local", "elastic", "local_and_elastic"}:
            return normalized
        raise ValueError("must be one of local, elastic, or local_and_elastic")

    @field_validator("queue_backend")
    @classmethod
    def validate_queue_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"local", "dramatiq"}:
            return normalized
        raise ValueError("must be one of local or dramatiq")

    @field_validator(
        "dispatch_queue_max_payload_bytes",
        "docling_perf_page_batch_size",
        mode="before",
    )
    @classmethod
    def normalize_optional_int(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return int(cleaned) if cleaned else None
        return value

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_dir / "outputs"

    @property
    def jobs_db_path(self) -> Path:
        return self.storage_dir / "jobs.sqlite3"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def service_config(self) -> ServiceConfig:
        return ServiceConfig(service_name=self.service_name)

    @property
    def storage_config(self) -> StorageConfig:
        return StorageConfig(
            storage_dir=self.storage_dir,
            uploads_dir=self.uploads_dir,
            outputs_dir=self.outputs_dir,
            jobs_db_path=self.jobs_db_path,
            retention_days=self.retention_days,
        )

    @property
    def upload_config(self) -> UploadConfig:
        return UploadConfig(
            max_upload_size_mb=self.max_upload_size_mb,
            allowed_upload_extensions=self.allowed_upload_extensions,
        )

    @property
    def docling_common_config(self) -> DoclingCommonConfig:
        return DoclingCommonConfig(
            allowed_formats=self.docling_allowed_formats,
            pipeline=self.docling_pipeline,
            accelerator_device=self.docling_accelerator_device,
            num_threads=self.docling_num_threads,
            cuda_use_flash_attention2=self.docling_cuda_use_flash_attention2,
            allow_external_plugins=self.docling_allow_external_plugins,
            engine_cache_enabled=self.docling_engine_cache_enabled,
            engine_warmup_enabled=self.docling_engine_warmup_enabled,
            engine_warmup_formats=self.docling_engine_warmup_formats,
            gpu_engine_concurrency=self.docling_gpu_engine_concurrency,
            gpu_batch_max_documents=self.docling_gpu_batch_max_documents,
            gpu_batch_wait_ms=self.docling_gpu_batch_wait_ms,
            engine_idle_ttl_seconds=self.docling_engine_idle_ttl_seconds,
            perf_page_batch_size=self.docling_perf_page_batch_size,
        )

    @property
    def docling_ocr_config(self) -> DoclingOcrConfig:
        return DoclingOcrConfig(
            do_ocr=self.docling_pdf_do_ocr,
            engine=self.docling_pdf_ocr_engine,
            languages=self.docling_pdf_ocr_languages,
            use_gpu=self.docling_pdf_ocr_use_gpu,
        )

    @property
    def docling_vlm_config(self) -> DoclingVlmConfig:
        return DoclingVlmConfig(
            model=self.docling_vlm_model,
            prompt=self.docling_vlm_prompt,
            response_format=self.docling_vlm_response_format,
            runtime=self.docling_vlm_runtime,
            scale=self.docling_vlm_scale,
            torch_dtype=self.docling_vlm_torch_dtype,
            load_in_8bit=self.docling_vlm_load_in_8bit,
            max_new_tokens=self.docling_vlm_max_new_tokens,
            trust_remote_code=self.docling_vlm_trust_remote_code,
            remote_llm_url=self.docling_remote_llm_url,
            remote_llm_model=self.docling_remote_llm_model,
            remote_llm_api_key_configured=self.docling_remote_llm_api_key is not None,
            remote_llm_api_key_header=self.docling_remote_llm_api_key_header,
            remote_llm_api_key_scheme=self.docling_remote_llm_api_key_scheme,
            remote_llm_timeout_seconds=self.docling_remote_llm_timeout_seconds,
            remote_llm_concurrency=self.docling_remote_llm_concurrency,
            remote_llm_page_batch_size=self.docling_remote_llm_page_batch_size,
            remote_llm_max_tokens=self.docling_remote_llm_max_tokens,
            remote_llm_temperature=self.docling_remote_llm_temperature,
            remote_llm_provider=self.docling_remote_llm_provider,
            remote_llm_health_check_enabled=self.docling_remote_llm_health_check_enabled,
            remote_llm_health_check_timeout_seconds=(
                self.docling_remote_llm_health_check_timeout_seconds
            ),
        )

    @property
    def docling_xbrl_config(self) -> DoclingXbrlConfig:
        return DoclingXbrlConfig(
            enable_local_fetch=self.docling_xbrl_enable_local_fetch,
            enable_remote_fetch=self.docling_xbrl_enable_remote_fetch,
            taxonomy_path=self.docling_xbrl_taxonomy_path,
        )

    @property
    def chunking_config(self) -> ChunkingConfig:
        return ChunkingConfig(
            enabled=self.chunking_enabled,
            strategy=self.chunking_strategy,
            max_tokens=self.chunk_max_tokens,
            tokenizer_model=self.chunk_tokenizer_model,
            merge_peers=self.chunk_merge_peers,
            repeat_table_header=self.chunk_repeat_table_header,
            omit_header_on_overflow=self.chunk_omit_header_on_overflow,
            omit_prefix_on_overflow=self.chunk_omit_prefix_on_overflow,
            chunk_size_chars=self.chunk_size_chars,
            chunk_overlap_chars=self.chunk_overlap_chars,
            embedding_output_enabled=self.embedding_output_enabled,
        )

    @property
    def confidence_config(self) -> ConfidenceConfig:
        return ConfidenceConfig(
            output_enabled=self.confidence_output_enabled,
            min_document_score=self.confidence_min_document_score,
            warn_only=self.confidence_warn_only,
        )

    @property
    def progress_config(self) -> ProgressConfig:
        return ProgressConfig(
            log_interval_seconds=self.progress_log_interval_seconds,
            page_interval=self.progress_page_interval,
            history_limit=self.progress_history_limit,
        )

    @property
    def dispatch_config(self) -> DispatchConfig:
        return DispatchConfig(
            parser_worker_count=self.parser_worker_count,
            dispatch_worker_count=self.dispatch_worker_count,
            queue_backend=self.queue_backend,
            rabbitmq_configured=bool(self.rabbitmq_url),
            dramatiq_parser_queue_name=self.dramatiq_parser_queue_name,
            dramatiq_dispatch_queue_name=self.dramatiq_dispatch_queue_name,
            queue_max_size=self.dispatch_queue_max_size,
            queue_max_payload_bytes=self.dispatch_queue_max_payload_bytes,
            max_bulk_size=self.dispatch_max_bulk_size,
            idle_interval_seconds=self.dispatch_idle_interval_seconds,
            sink_mode=self.dispatch_sink_mode,
            max_retries=self.dispatch_max_retries,
            elastic_url=self.embedding_elastic_url,
            elastic_username=self.embedding_elastic_username,
            elastic_password_configured=self.embedding_elastic_password is not None,
            elastic_index=self.embedding_elastic_index,
            elastic_mapping_version=self.embedding_elastic_mapping_version,
            elastic_pipeline=self.embedding_elastic_pipeline,
            elastic_verify_certs=self.embedding_elastic_verify_certs,
            elastic_request_timeout_seconds=self.embedding_elastic_request_timeout_seconds,
            elastic_max_retries=self.embedding_elastic_max_retries,
        )

    @property
    def embedding_queue_config(self) -> EmbeddingQueueConfig:
        return EmbeddingQueueConfig(**self.dispatch_config.model_dump())


@lru_cache
def get_settings() -> Settings:
    return Settings()
