import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "ingest-orquestator-server"
    storage_dir: Path = Path(".data")
    max_upload_size_mb: int = Field(default=100, ge=1)
    docling_accelerator_device: str = Field(
        default="auto",
        description="Docling accelerator device: auto, cpu, cuda, cuda:N, mps, or xpu.",
    )
    docling_num_threads: int = Field(default=4, ge=1)
    docling_cuda_use_flash_attention2: bool = False
    docling_pdf_do_ocr: bool = True
    docling_pdf_do_table_structure: bool = True
    docling_pdf_ocr_batch_size: int = Field(default=4, ge=1)
    docling_pdf_layout_batch_size: int = Field(default=4, ge=1)
    docling_pdf_table_batch_size: int = Field(default=4, ge=1)
    docling_pdf_queue_max_size: int = Field(default=100, ge=1)

    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    @field_validator("docling_accelerator_device")
    @classmethod
    def validate_docling_accelerator_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"auto", "cpu", "cuda", "mps", "xpu"}:
            return normalized
        if re.fullmatch(r"cuda:\d+", normalized):
            return normalized
        raise ValueError("must be one of auto, cpu, cuda, cuda:N, mps, or xpu")

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_dir / "outputs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
