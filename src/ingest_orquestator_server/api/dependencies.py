from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.infrastructure.filesystem.local_upload_storage import (
    LocalUploadStorage,
)

SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_parser_registry(settings: SettingsDependency) -> ParserRegistry:
    return ParserRegistry(
        {
            "docling": lambda: DoclingDocumentParser(settings=settings),
        }
    )


def get_document_parse_service(
    parser_registry: Annotated[ParserRegistry, Depends(get_parser_registry)],
) -> DocumentParseService:
    return DocumentParseService(
        parser_registry=parser_registry,
        output_writer=LocalParseOutputWriter(),
    )


def get_file_ingestion_service(
    settings: SettingsDependency,
    document_parse_service: Annotated[
        DocumentParseService,
        Depends(get_document_parse_service),
    ],
) -> FileIngestionService:
    return FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(),
        document_parse_service=document_parse_service,
    )
