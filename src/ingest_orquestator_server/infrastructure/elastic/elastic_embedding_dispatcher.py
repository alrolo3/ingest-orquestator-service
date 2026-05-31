from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from elasticsearch import Elasticsearch, TransportError, helpers

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
)


class ElasticEmbeddingDispatchError(RuntimeError):
    pass


BulkHelper = Callable[..., tuple[int, int | list[dict[str, Any]]]]


class ElasticEmbeddingDispatcher:
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

    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        if not items:
            raise ElasticEmbeddingDispatchError("Cannot submit an empty embedding batch.")

        documents = [document for item in items for document in self._chunk_documents(item)]
        if not documents:
            return EmbeddingDispatchResult(
                accepted_document_count=len(items),
                accepted_chunk_count=0,
                raw_response={
                    "client": "elasticsearch",
                    "mode": "bulk",
                    "mapping_version": self._settings.embedding_elastic_mapping_version,
                    "successful": 0,
                    "errors": [],
                },
            )
        return self._submit_bulk(documents, document_count=len(items))

    def _chunk_documents(self, item: EmbeddingQueueItem) -> list[dict[str, Any]]:
        records = [record.model_dump(mode="json") for record in item.embedding_records]
        return [self._chunk_document(item, record) for record in records]

    def _chunk_document(self, item: EmbeddingQueueItem, record: dict[str, Any]) -> dict[str, Any]:
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        else:
            metadata = dict(metadata)
            if not self._settings.embedding_elastic_include_local_paths:
                metadata.pop("source_path", None)

        content = str(record.get("text") or "")
        document_id = str(record.get("document_id") or item.document_id)
        chunk_id = str(record.get("chunk_id") or record.get("record_id") or item.queue_id)
        record_id = str(record.get("record_id") or f"{document_id}:{chunk_id}")
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        title = str(metadata.get("title") or item.source_file_name or document_id)
        confidence = metadata.get("confidence")
        if not isinstance(confidence, dict):
            confidence = {}

        document = {
            "record_id": record_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "schema_version": record.get("schema_version"),
            "content": content,
            "raw_text": record.get("raw_text"),
            "contextualized": bool(record.get("contextualized")),
            "source_file_name": metadata.get("source_file_name") or item.source_file_name,
            "title": title,
            "mime_type": metadata.get("mime_type"),
            "input_format": metadata.get("input_format") or item.metadata.get("input_format"),
            "parser": metadata.get("parser") or item.metadata.get("parser"),
            "pipeline": metadata.get("pipeline") or item.metadata.get("pipeline"),
            "vlm_model": metadata.get("vlm_model"),
            "vlm_runtime": metadata.get("vlm_runtime"),
            "picture_description_model": metadata.get("picture_description_model"),
            "picture_description_runtime": metadata.get("picture_description_runtime"),
            "chunker_strategy": metadata.get("chunker_strategy"),
            "page_start": page_start,
            "page_end": page_end,
            "element_ids": metadata.get("element_ids", []),
            "element_types": metadata.get("element_types", []),
            "confidence": confidence,
            "runtime": metadata.get("runtime"),
            "metadata": metadata,
        }
        return document

    def _submit_bulk(
        self,
        documents: list[dict[str, Any]],
        *,
        document_count: int,
    ) -> EmbeddingDispatchResult:
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
            raise ElasticEmbeddingDispatchError(
                f"Elastic bulk request failed: {self._safe_exception_message(exc)}"
            ) from exc
        except Exception as exc:
            raise ElasticEmbeddingDispatchError(
                f"Elastic bulk request failed: {self._safe_exception_message(exc)}"
            ) from exc

        if errors:
            raise ElasticEmbeddingDispatchError(
                f"Elastic bulk request returned item errors: {self._safe_payload(errors)}"
            )

        return EmbeddingDispatchResult(
            accepted_document_count=document_count,
            accepted_chunk_count=int(successful),
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
            raise ElasticEmbeddingDispatchError(
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
