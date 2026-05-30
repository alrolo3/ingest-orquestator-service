from ingest_orquestator_server.application.ports.document_parser import DocumentParser
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)

__all__ = ["DoclingDocumentParser", "DocumentParser"]
