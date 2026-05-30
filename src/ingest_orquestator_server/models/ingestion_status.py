from enum import StrEnum


class IngestionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
