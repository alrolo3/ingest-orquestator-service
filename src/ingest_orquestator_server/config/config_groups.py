from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ServiceConfig(BaseModel):
    service_name: str


class StorageConfig(BaseModel):
    storage_dir: Path
    uploads_dir: Path
    outputs_dir: Path
    jobs_db_path: Path
    retention_days: int


class UploadConfig(BaseModel):
    max_upload_size_mb: int
    allowed_upload_extensions: list[str]


class DoclingCommonConfig(BaseModel):
    allowed_formats: list[str]
    pipeline: str
    profile: str
    accelerator_device: str
    num_threads: int
    cuda_use_flash_attention2: bool
    allow_external_plugins: bool


class DoclingOcrConfig(BaseModel):
    do_ocr: bool
    engine: str
    languages: list[str]
    use_gpu: bool | None


class DoclingVlmConfig(BaseModel):
    model: str
    prompt: str
    response_format: str
    runtime: str
    scale: float
    torch_dtype: str | None
    load_in_8bit: bool


class DoclingXbrlConfig(BaseModel):
    enable_local_fetch: bool
    enable_remote_fetch: bool
    taxonomy_path: Path | None


class ChunkingConfig(BaseModel):
    enabled: bool
    strategy: str
    max_tokens: int
    tokenizer_model: str | None
    merge_peers: bool
    repeat_table_header: bool
    omit_header_on_overflow: bool
    omit_prefix_on_overflow: bool
    chunk_size_chars: int
    chunk_overlap_chars: int
    embedding_output_enabled: bool


class ConfidenceConfig(BaseModel):
    output_enabled: bool
    min_document_score: float | None
    warn_only: bool
