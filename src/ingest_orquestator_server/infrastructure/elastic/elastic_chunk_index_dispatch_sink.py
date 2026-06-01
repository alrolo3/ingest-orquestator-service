from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from elasticsearch import Elasticsearch, TransportError, helpers

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.parsed_document_dispatch import (
    DispatchSinkResult,
    ParsedDocumentDispatchItem,
)
from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord


class ElasticChunkIndexDispatchError(RuntimeError):
    pass


BulkHelper = Callable[..., tuple[int, int | list[dict[str, Any]]]]

INDEXED_CONFIDENCE_FIELDS = (
    "parse_score",
    "layout_score",
    "table_score",
    "ocr_score",
    "mean_score",
    "low_score",
    "mean_grade",
    "low_grade",
)
REQUIRED_INDEX_FIELDS = {"record_id", "document_id", "content", "title", "record_type"}


class ElasticChunkIndexDispatchSink:
    def __init__(
        self,
        settings: Settings,
        *,
        client: Elasticsearch | None = None,
        bulk_helper: BulkHelper = helpers.bulk,
    ) -> None:
        self._settings = settings
        self._client = client
        self._bulk_helper = bulk_helper

    def submit_batch(self, items: list[ParsedDocumentDispatchItem]) -> DispatchSinkResult:
        if not items:
            raise ElasticChunkIndexDispatchError("Cannot submit an empty RAG record batch.")

        documents = [document for item in items for document in self._record_documents(item)]
        if not documents:
            return DispatchSinkResult(
                accepted_document_count=len(items),
                accepted_record_count=0,
                raw_response={
                    "client": "elasticsearch",
                    "mode": "bulk",
                    "mapping_version": self._settings.embedding_elastic_mapping_version,
                    "successful": 0,
                    "errors": [],
                },
            )
        return self._submit_bulk(documents, document_count=len(items))

    def _record_documents(self, item: ParsedDocumentDispatchItem) -> list[dict[str, Any]]:
        return [self._record_document(item, record) for record in item.content.rag_records]

    def _record_document(
        self,
        item: ParsedDocumentDispatchItem,
        record: RagIngestionRecord,
    ) -> dict[str, Any]:
        metadata = dict(record.metadata)
        confidence = self._indexable_confidence(
            metadata.get("confidence_summary") or item.content.metadata.get("confidence_summary")
        )
        document = {
            "record_id": record.record_id,
            "document_id": record.document_id,
            "job_id": record.job_id,
            "chunk_id": record.chunk_id,
            "record_type": record.record_type.value,
            "content": record.content,
            "source_file_name": record.source_file_name or item.source_file_name,
            "title": record.title or item.source_file_name or record.document_id,
            "input_format": record.input_format or item.metadata.get("input_format"),
            "parser": record.parser or item.metadata.get("parser"),
            "pipeline": record.pipeline or item.metadata.get("pipeline"),
            "chunker_strategy": metadata.get("chunker_strategy"),
            "page_start": record.page_start,
            "page_end": record.page_end,
            "element_types": metadata.get("element_types", []),
            "confidence": confidence,
            "metadata": self._safe_record_metadata(metadata),
        }
        return self._drop_empty_optional_fields(document)

    def _safe_record_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in metadata.items()
            if key not in {"source_path", "raw_text"} and not self._is_empty_optional_value(value)
        }

    def _indexable_confidence(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {
            key: value[key]
            for key in INDEXED_CONFIDENCE_FIELDS
            if key in value and value[key] is not None
        }

    def _drop_empty_optional_fields(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in document.items()
            if key in REQUIRED_INDEX_FIELDS or not self._is_empty_optional_value(value)
        }

    def _is_empty_optional_value(self, value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    def _submit_bulk(
        self,
        documents: list[dict[str, Any]],
        *,
        document_count: int,
    ) -> DispatchSinkResult:
        actions = [self._bulk_action(document) for document in documents]
        try:
            successful, errors = self._bulk_helper(
                self._elastic_client(),
                actions,
                stats_only=False,
                raise_on_error=False,
                request_timeout=self._settings.embedding_elastic_request_timeout_seconds,
            )
        except TransportError as exc:
            raise ElasticChunkIndexDispatchError(
                f"Elastic bulk request failed: {self._safe_exception_message(exc)}"
            ) from exc
        except Exception as exc:
            raise ElasticChunkIndexDispatchError(
                f"Elastic bulk request failed: {self._safe_exception_message(exc)}"
            ) from exc

        if errors:
            raise ElasticChunkIndexDispatchError(
                f"Elastic bulk request returned item errors: {self._safe_payload(errors)}"
            )

        return DispatchSinkResult(
            accepted_document_count=document_count,
            accepted_record_count=int(successful),
            raw_response={
                "client": "elasticsearch",
                "mode": "bulk",
                "mapping_version": self._settings.embedding_elastic_mapping_version,
                "successful": int(successful),
                "errors": [],
            },
        )

    def _bulk_action(self, document: dict[str, Any]) -> dict[str, Any]:
        action = {
            "_op_type": "index",
            "_index": self._settings.embedding_elastic_index,
            "_id": document["record_id"],
            "_source": document,
        }
        if self._uses_ingest_pipeline:
            action["pipeline"] = self._settings.embedding_elastic_pipeline
        return action

    @property
    def _uses_semantic_text_mapping(self) -> bool:
        return self._settings.embedding_elastic_mapping_version == "v2"

    @property
    def _uses_ingest_pipeline(self) -> bool:
        return (
            self._settings.embedding_elastic_pipeline is not None
            and not self._uses_semantic_text_mapping
        )

    def _elastic_client(self) -> Elasticsearch:
        if self._client is not None:
            return self._client
        if self._settings.embedding_elastic_url is None:
            raise ElasticChunkIndexDispatchError(
                "INGEST_EMBEDDING_ELASTIC_URL must be configured when "
                "INGEST_DISPATCH_SINK_MODE includes elastic."
            )

        basic_auth = None
        if self._settings.embedding_elastic_username and self._settings.embedding_elastic_password:
            basic_auth = (
                self._settings.embedding_elastic_username,
                self._settings.embedding_elastic_password,
            )

        self._client = Elasticsearch(
            self._settings.embedding_elastic_url,
            basic_auth=basic_auth,
            verify_certs=self._settings.embedding_elastic_verify_certs,
            ssl_show_warn=self._settings.embedding_elastic_verify_certs,
            request_timeout=self._settings.embedding_elastic_request_timeout_seconds,
            max_retries=self._settings.embedding_elastic_max_retries,
            retry_on_timeout=True,
        )
        return self._client

    def _safe_payload(self, payload: Any) -> str:
        text = json.dumps(payload, default=str)
        password = self._settings.embedding_elastic_password
        if password:
            text = text.replace(password, "[redacted]")
        return text

    def _safe_exception_message(self, exc: Exception) -> str:
        message = str(exc)
        password = self._settings.embedding_elastic_password
        if password:
            message = message.replace(password, "[redacted]")
        return message
