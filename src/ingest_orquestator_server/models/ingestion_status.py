from enum import StrEnum


class IngestionStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EMBEDDING_QUEUED = "embedding_queued"
    SENT_TO_EMBEDDING_SYSTEM = "sent_to_embedding_system"
    EMBEDDING_TASK_RUNNING = "embedding_task_running"
    EMBEDDING_COMPLETED = "embedding_completed"
    EMBEDDING_FAILED = "embedding_failed"
