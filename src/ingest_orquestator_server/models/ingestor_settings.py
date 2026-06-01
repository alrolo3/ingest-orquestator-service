from typing import Any, Literal

from pydantic import BaseModel, Field

SettingSource = Literal["env", "sqlite"]
SettingKind = Literal["boolean", "integer", "number", "text", "list", "secret", "select"]


class IngestorSettingOption(BaseModel):
    value: str
    label: str


class IngestorSettingField(BaseModel):
    key: str
    env_var: str
    label: str
    group: str
    kind: SettingKind
    value: Any = None
    source: SettingSource
    configured: bool = False
    secret: bool = False
    options: list[IngestorSettingOption] = Field(default_factory=list)


class IngestorSettingsResponse(BaseModel):
    fields: list[IngestorSettingField]
    boot_time_keys: list[str]


class IngestorSettingsUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    reset_keys: list[str] = Field(default_factory=list)
