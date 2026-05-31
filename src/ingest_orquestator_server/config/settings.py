import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingest_orquestator_server.config.config_groups import (
    ChunkingConfig,
    ConfidenceConfig,
    DoclingCommonConfig,
    DoclingOcrConfig,
    DoclingVlmConfig,
    DoclingXbrlConfig,
    EmbeddingQueueConfig,
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
    docling_vlm_trust_remote_code: bool | None = None
    docling_vllm_tensor_parallel_size: int = Field(default=1, ge=1)
    docling_vllm_gpu_memory_utilization: float = Field(default=0.9, gt=0, le=1)
    docling_vllm_trust_remote_code: bool = False
    docling_vllm_cudagraph_mode: str = "PIECEWISE"
    docling_vllm_model_impl: str = "auto"
    docling_vllm_enforce_eager: bool | None = None
    docling_vllm_max_model_len: int | None = Field(default=None, ge=1)
    docling_vllm_max_num_batched_tokens: int | None = Field(default=None, ge=1)
    docling_vllm_fallback_runtime: str = "transformers"
    docling_vllm_fallback_on_unsupported: bool = True
    docling_vllm_allow_unverified_models: bool = False
    docling_xbrl_enable_local_fetch: bool = False
    docling_xbrl_enable_remote_fetch: bool = False
    docling_xbrl_taxonomy_path: Path | None = None
    embedding_output_enabled: bool = True
    embedding_queue_enabled: bool = False
    embedding_queue_max_bulk_size: int = Field(default=5, ge=1, le=5)
    embedding_elastic_url: str | None = None
    embedding_elastic_username: str | None = None
    embedding_elastic_password: str | None = None
    embedding_elastic_index: str = "ingest-embedding-input"
    embedding_elastic_pipeline: str | None = None
    embedding_elastic_submit_method: str = "POST"
    embedding_elastic_submit_path: str = "/_bulk"
    embedding_elastic_task_id_field: str = "task"
    embedding_elastic_task_status_path_template: str = "/_tasks/{task_id}"
    embedding_elastic_verify_certs: bool = True
    embedding_elastic_request_timeout_seconds: float = Field(default=30.0, gt=0)
    embedding_elastic_task_poll_interval_seconds: float = Field(default=2.0, gt=0)
    embedding_elastic_task_timeout_seconds: float = Field(default=300.0, gt=0)
    embedding_elastic_max_retries: int = Field(default=3, ge=0)
    embedding_elastic_include_local_paths: bool = False

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
        normalized = value.strip().lower()
        if normalized in {"auto", "auto_inline", "transformers", "vllm"}:
            return normalized
        raise ValueError("must be one of auto, auto_inline, transformers, or vllm")

    @field_validator("docling_pdf_picture_description_runtime")
    @classmethod
    def validate_docling_pdf_picture_description_runtime(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"auto", "auto_inline", "transformers", "vllm"}:
            return normalized
        raise ValueError("must be one of auto, auto_inline, transformers, or vllm")

    @field_validator("docling_vllm_fallback_runtime")
    @classmethod
    def validate_docling_vllm_fallback_runtime(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"auto_inline", "transformers"}:
            return normalized
        raise ValueError("must be one of auto_inline or transformers")

    @field_validator("docling_vllm_cudagraph_mode")
    @classmethod
    def validate_docling_vllm_cudagraph_mode(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized in {
            "NONE",
            "FULL",
            "PIECEWISE",
            "FULL_AND_PIECEWISE",
            "FULL_DECODE_ONLY",
        }:
            return normalized
        raise ValueError(
            "must be one of NONE, FULL, PIECEWISE, FULL_AND_PIECEWISE, or FULL_DECODE_ONLY"
        )

    @field_validator("allowed_upload_extensions", mode="before")
    @classmethod
    def parse_allowed_upload_extensions(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

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
        mode="before",
    )
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator(
        "embedding_elastic_submit_path",
        "embedding_elastic_task_status_path_template",
    )
    @classmethod
    def normalize_elastic_path(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned if cleaned.startswith("/") else f"/{cleaned}"

    @field_validator("embedding_elastic_index")
    @classmethod
    def normalize_embedding_elastic_index(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("embedding_elastic_submit_method")
    @classmethod
    def validate_embedding_elastic_submit_method(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"POST", "PUT"}:
            raise ValueError("must be POST or PUT")
        return normalized

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
            trust_remote_code=self.effective_docling_vlm_trust_remote_code,
            vllm_tensor_parallel_size=self.docling_vllm_tensor_parallel_size,
            vllm_gpu_memory_utilization=self.docling_vllm_gpu_memory_utilization,
            vllm_trust_remote_code=self.docling_vllm_trust_remote_code,
            vllm_cudagraph_mode=self.docling_vllm_cudagraph_mode,
            vllm_model_impl=self.docling_vllm_model_impl,
            vllm_enforce_eager=self.docling_vllm_enforce_eager,
            vllm_max_model_len=self.docling_vllm_max_model_len,
            vllm_max_num_batched_tokens=self.docling_vllm_max_num_batched_tokens,
            vllm_fallback_runtime=self.docling_vllm_fallback_runtime,
            vllm_fallback_on_unsupported=self.docling_vllm_fallback_on_unsupported,
            vllm_allow_unverified_models=self.docling_vllm_allow_unverified_models,
        )

    @property
    def effective_docling_vlm_trust_remote_code(self) -> bool:
        if self.docling_vlm_trust_remote_code is not None:
            return self.docling_vlm_trust_remote_code
        return self.docling_vllm_trust_remote_code

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
    def embedding_queue_config(self) -> EmbeddingQueueConfig:
        return EmbeddingQueueConfig(
            enabled=self.embedding_queue_enabled,
            max_bulk_size=self.embedding_queue_max_bulk_size,
            elastic_url=self.embedding_elastic_url,
            elastic_username=self.embedding_elastic_username,
            elastic_password_configured=self.embedding_elastic_password is not None,
            elastic_index=self.embedding_elastic_index,
            elastic_pipeline=self.embedding_elastic_pipeline,
            elastic_submit_method=self.embedding_elastic_submit_method,
            elastic_submit_path=self.embedding_elastic_submit_path,
            elastic_task_id_field=self.embedding_elastic_task_id_field,
            elastic_task_status_path_template=self.embedding_elastic_task_status_path_template,
            elastic_verify_certs=self.embedding_elastic_verify_certs,
            elastic_request_timeout_seconds=self.embedding_elastic_request_timeout_seconds,
            elastic_task_poll_interval_seconds=self.embedding_elastic_task_poll_interval_seconds,
            elastic_task_timeout_seconds=self.embedding_elastic_task_timeout_seconds,
            elastic_max_retries=self.embedding_elastic_max_retries,
            elastic_include_local_paths=self.embedding_elastic_include_local_paths,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
