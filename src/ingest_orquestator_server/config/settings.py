import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
            ".pdf",
            ".md",
            ".markdown",
            ".txt",
            ".html",
            ".htm",
            ".docx",
            ".pptx",
        ]
    )
    chunk_size_chars: int = Field(default=1200, ge=100)
    chunk_overlap_chars: int = Field(default=150, ge=0)
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
    docling_pdf_picture_description_prompt: str = DOCLING_PICTURE_DESCRIPTION_PROMPT
    docling_pdf_do_code_enrichment: bool = True
    docling_pdf_do_formula_enrichment: bool = True
    docling_pdf_code_formula_preset: str = DOCLING_CODE_FORMULA_PRESET
    docling_pdf_ocr_batch_size: int = Field(default=4, ge=1)
    docling_pdf_layout_batch_size: int = Field(default=4, ge=1)
    docling_pdf_table_batch_size: int = Field(default=4, ge=1)
    docling_pdf_queue_max_size: int = Field(default=100, ge=1)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
