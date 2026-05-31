from enum import StrEnum


class IngestionStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PARSER_QUEUED = "parser_queued"
    PARSING = "parsing"
    PARSED = "parsed"
    COMPLETED = "completed"
    FAILED = "failed"
    DISPATCH_QUEUED = "dispatch_queued"
    DISPATCHING = "dispatching"
    STORED_LOCAL = "stored_local"
    INDEXED_ELASTIC = "indexed_elastic"
    RETRYABLE_FAILURE = "retryable_failure"
