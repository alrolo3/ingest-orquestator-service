from __future__ import annotations

from uuid import uuid4

from ingest_orquestator_server.application.ports.upload_file import UploadFileLike
from ingest_orquestator_server.application.ports.upload_storage import UploadStorage
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_status import IngestionStatus


class FileIngestionService:
    def __init__(
        self,
        *,
        settings: Settings,
        upload_storage: UploadStorage,
        document_parse_service: DocumentParseService,
    ) -> None:
        self._settings = settings
        self._upload_storage = upload_storage
        self._document_parse_service = document_parse_service

    async def ingest_upload(
        self,
        *,
        upload: UploadFileLike,
        parser_name: str,
        include_document: bool,
    ) -> IngestResponse:
        job_id = str(uuid4())
        upload_path = await self._upload_storage.save(
            upload,
            self._settings.uploads_dir,
            job_id=job_id,
        )
        parse_result = self._document_parse_service.parse_file(
            file_path=upload_path,
            parser_name=parser_name,
            output_root=self._settings.outputs_dir,
            document_id=job_id,
        )

        return IngestResponse(
            job_id=job_id,
            status=IngestionStatus.COMPLETED,
            parser=parser_name,
            document_id=parse_result.parse_output.document.document_id,
            input_path=upload_path,
            outputs=parse_result.outputs,
            document=parse_result.parse_output.document if include_document else None,
        )
