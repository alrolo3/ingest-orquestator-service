from pydantic import BaseModel

from ingest_orquestator_server.models.ingestion_status import IngestionStatus


class JobRemovalResult(BaseModel):
    job_id: str
    previous_status: IngestionStatus
    removed: bool = True
    parser_process_terminated: bool = False
    parser_process_signal: int | None = None
    parser_process_error: str | None = None
    removed_dispatch_queue_item: bool = False
    removed_artifact_count: int = 0
