from types import NoneType, UnionType
from typing import get_args, get_origin

from ingest_orquestator_server.application.ports.ingestor_settings_repository import (
    IngestorSettingsRepository,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestor_settings import (
    IngestorSettingField,
    IngestorSettingOption,
    IngestorSettingsResponse,
    IngestorSettingsUpdate,
    SettingKind,
)

BOOT_TIME_SETTING_KEYS = {
    "storage_dir",
    "cors_allow_origins",
    "queue_backend",
    "rabbitmq_url",
    "dramatiq_parser_queue_name",
    "dramatiq_dispatch_queue_name",
    "dramatiq_parser_time_limit_ms",
    "dramatiq_dispatch_time_limit_ms",
    "parser_process_count",
    "parser_threads_per_process",
    "parser_worker_count",
    "dispatch_process_count",
    "dispatch_threads_per_process",
}

SECRET_SETTING_KEYS = {
    "docling_remote_llm_api_key",
    "embedding_elastic_password",
}

SETTING_OPTIONS = {
    "docling_pipeline": ["standard", "vlm", "auto"],
    "chunking_strategy": ["page", "token", "line"],
    "dispatch_sink_mode": ["local", "elastic", "local_and_elastic"],
    "embedding_elastic_mapping_version": ["v1", "v2"],
    "docling_vlm_response_format": [
        "markdown",
        "doctags",
        "doclang",
        "deepseekocr_markdown",
        "html",
        "otsl",
        "plaintext",
    ],
    "docling_remote_llm_provider": ["openai_compatible"],
    "docling_pdf_table_structure_backend": ["tableformer"],
}


class IngestorSettingsService:
    def __init__(
        self,
        *,
        base_settings: Settings,
        repository: IngestorSettingsRepository,
    ) -> None:
        self._base_settings = base_settings
        self._repository = repository

    def effective_settings(self) -> Settings:
        return self._settings_with_overrides(self._repository.list())

    def settings_response(self) -> IngestorSettingsResponse:
        overrides = self._repository.list()
        settings = self._settings_with_overrides(overrides)
        settings_values = settings.model_dump(mode="json")
        fields = [
            self._setting_field(key, value=settings_values[key], source_key_exists=key in overrides)
            for key in self._runtime_setting_keys()
        ]
        return IngestorSettingsResponse(
            fields=sorted(fields, key=lambda field: (field.group, field.label)),
            boot_time_keys=sorted(BOOT_TIME_SETTING_KEYS),
        )

    def update(self, update: IngestorSettingsUpdate) -> IngestorSettingsResponse:
        repeated_keys = set(update.values) & set(update.reset_keys)
        if repeated_keys:
            raise ValueError(
                f"Setting cannot be updated and reset at the same time: {repeated_keys}"
            )

        self._validate_keys([*update.values, *update.reset_keys])

        overrides = self._repository.list()
        for key in update.reset_keys:
            overrides.pop(key, None)
        for key, value in update.values.items():
            overrides[key] = self._normalize_empty_value(key, value)

        validated_settings = self._settings_with_overrides(overrides)
        normalized_values = validated_settings.model_dump(mode="json")

        for key in update.reset_keys:
            self._repository.delete(key)
        for key in update.values:
            self._repository.set(key, normalized_values[key])

        return self.settings_response()

    def _settings_with_overrides(self, overrides: dict[str, object]) -> Settings:
        values = self._base_settings.model_dump(mode="python")
        values.update(overrides)
        return Settings(**values)

    def _setting_field(
        self,
        key: str,
        *,
        value: object,
        source_key_exists: bool,
    ) -> IngestorSettingField:
        secret = key in SECRET_SETTING_KEYS
        configured = value is not None and value != ""
        return IngestorSettingField(
            key=key,
            env_var=f"INGEST_{key.upper()}",
            label=_label_for_key(key),
            group=_group_for_key(key),
            kind=_kind_for_key(key),
            value=None if secret else value,
            source="sqlite" if source_key_exists else "env",
            configured=configured,
            secret=secret,
            options=_options_for_key(key),
        )

    @staticmethod
    def _runtime_setting_keys() -> list[str]:
        return [
            key
            for key in Settings.model_fields
            if key not in BOOT_TIME_SETTING_KEYS
        ]

    def _validate_keys(self, keys: list[str]) -> None:
        for key in keys:
            if key not in Settings.model_fields:
                raise ValueError(f"Unknown setting: {key}")
            if key in BOOT_TIME_SETTING_KEYS:
                raise ValueError(f"Setting is not runtime-configurable: {key}")

    @staticmethod
    def _normalize_empty_value(key: str, value: object) -> object:
        field = Settings.model_fields[key]
        if value == "" and _allows_none(field.annotation):
            return None
        return value


def _kind_for_key(key: str) -> SettingKind:
    if key in SECRET_SETTING_KEYS:
        return "secret"
    if key in SETTING_OPTIONS:
        return "select"

    annotation = Settings.model_fields[key].annotation
    if _contains_type(annotation, bool):
        return "boolean"
    if _contains_type(annotation, int):
        return "integer"
    if _contains_type(annotation, float):
        return "number"
    if _contains_type(annotation, list):
        return "list"
    return "text"


def _contains_type(annotation: object, expected: type) -> bool:
    if annotation is expected:
        return True
    origin = get_origin(annotation)
    if origin in {UnionType, list}:
        return expected is list if origin is list else any(
            _contains_type(argument, expected) for argument in get_args(annotation)
        )
    return False


def _allows_none(annotation: object) -> bool:
    if annotation is NoneType:
        return True
    origin = get_origin(annotation)
    if origin is UnionType:
        return any(argument is NoneType for argument in get_args(annotation))
    return False


def _options_for_key(key: str) -> list[IngestorSettingOption]:
    return [
        IngestorSettingOption(value=value, label=_label_for_key(value))
        for value in SETTING_OPTIONS.get(key, [])
    ]


def _label_for_key(key: str) -> str:
    return key.replace("_", " ").replace("llm", "LLM").replace("vlm", "VLM").title()


def _group_for_key(key: str) -> str:
    if key in {"service_name", "retention_days"}:
        return "Service"
    if key in {"max_upload_size_mb", "allowed_upload_extensions"}:
        return "Upload"
    if key.startswith("docling_remote_llm"):
        return "Remote LLM"
    if key.startswith("docling_vlm"):
        return "Docling VLM"
    if key.startswith("docling_pdf"):
        return "Docling PDF"
    if key.startswith("docling_xbrl"):
        return "Docling XBRL"
    if key.startswith("docling"):
        return "Docling runtime"
    if key.startswith("chunk") or key == "embedding_output_enabled":
        return "Chunking"
    if key.startswith("embedding_elastic") or key.startswith("dispatch"):
        return "Dispatch"
    if key.startswith("parser"):
        return "Parser"
    if key.startswith("confidence"):
        return "Confidence"
    if key.startswith("progress"):
        return "Progress"
    return "Other"
