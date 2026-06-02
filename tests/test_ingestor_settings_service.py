import pytest
from pydantic import ValidationError

from ingest_orquestator_server.application.services.ingestor_settings_service import (
    IngestorSettingsService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestor_settings_repository import (
    SqliteIngestorSettingsRepository,
)
from ingest_orquestator_server.models.ingestor_settings import IngestorSettingsUpdate


def test_ingestor_settings_service_persists_effective_settings(tmp_path) -> None:
    repository = SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3")
    base_settings = Settings(storage_dir=tmp_path, docling_accelerator_device="cpu")

    service = IngestorSettingsService(base_settings=base_settings, repository=repository)
    response = service.update(
        IngestorSettingsUpdate(
            values={
                "docling_accelerator_device": "cuda",
                "max_upload_size_mb": 256,
            }
        )
    )

    persisted_service = IngestorSettingsService(
        base_settings=base_settings,
        repository=SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3"),
    )
    effective_settings = persisted_service.effective_settings()
    accelerator_field = next(
        field for field in response.fields if field.key == "docling_accelerator_device"
    )

    assert effective_settings.docling_accelerator_device == "cuda"
    assert effective_settings.max_upload_size_mb == 256
    assert accelerator_field.source == "sqlite"
    assert accelerator_field.value == "cuda"


def test_ingestor_settings_service_redacts_write_only_secrets(tmp_path) -> None:
    repository = SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3")
    service = IngestorSettingsService(
        base_settings=Settings(storage_dir=tmp_path),
        repository=repository,
    )

    response = service.update(
        IngestorSettingsUpdate(values={"embedding_elastic_password": "secret-password"})
    )
    secret_field = next(
        field for field in response.fields if field.key == "embedding_elastic_password"
    )

    assert service.effective_settings().embedding_elastic_password == "secret-password"
    assert secret_field.secret is True
    assert secret_field.configured is True
    assert secret_field.value is None
    assert "secret-password" not in response.model_dump_json()


def test_ingestor_settings_service_resets_to_env_baseline(tmp_path) -> None:
    repository = SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3")
    base_settings = Settings(storage_dir=tmp_path, docling_accelerator_device="cpu")
    service = IngestorSettingsService(base_settings=base_settings, repository=repository)

    service.update(IngestorSettingsUpdate(values={"docling_accelerator_device": "cuda"}))
    service.update(IngestorSettingsUpdate(reset_keys=["docling_accelerator_device"]))

    assert service.effective_settings().docling_accelerator_device == "cpu"


def test_ingestor_settings_service_loads_env_then_sqlite_overrides(tmp_path) -> None:
    repository = SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3")
    base_settings = Settings(
        storage_dir=tmp_path,
        chunk_tokenizer_path="/datastore/tokenizers/qwen3-embedding-8b",
    )
    repository.set(
        "chunk_tokenizer_path",
        "/datastore/models/tokenizers/qwen3-embedding-8b",
    )

    service = IngestorSettingsService(base_settings=base_settings, repository=repository)

    assert (
        str(service.effective_settings().chunk_tokenizer_path)
        == "/datastore/models/tokenizers/qwen3-embedding-8b"
    )


def test_ingestor_settings_service_rejects_boot_time_and_unknown_keys(tmp_path) -> None:
    service = IngestorSettingsService(
        base_settings=Settings(storage_dir=tmp_path),
        repository=SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3"),
    )

    with pytest.raises(ValueError, match="not runtime-configurable"):
        service.update(IngestorSettingsUpdate(values={"storage_dir": ".other"}))

    with pytest.raises(ValueError, match="Unknown setting"):
        service.update(IngestorSettingsUpdate(values={"does_not_exist": True}))


def test_ingestor_settings_service_validates_settings_values(tmp_path) -> None:
    service = IngestorSettingsService(
        base_settings=Settings(storage_dir=tmp_path),
        repository=SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3"),
    )

    with pytest.raises(ValidationError):
        service.update(IngestorSettingsUpdate(values={"docling_accelerator_device": "gpu"}))


def test_ingestor_settings_service_exposes_elastic_mapping_v3_option(tmp_path) -> None:
    service = IngestorSettingsService(
        base_settings=Settings(storage_dir=tmp_path),
        repository=SqliteIngestorSettingsRepository(tmp_path / "jobs.sqlite3"),
    )

    response = service.settings_response()
    mapping_field = next(
        field for field in response.fields if field.key == "embedding_elastic_mapping_version"
    )

    assert [option.value for option in mapping_field.options] == ["v1", "v2", "v3"]
