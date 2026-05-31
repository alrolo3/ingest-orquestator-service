from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch, TransportError, helpers

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
    EmbeddingTaskStatus,
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
        if "_bulk" in self._settings.embedding_elastic_submit_path:
            return self._submit_bulk(documents)

        response = self._perform_request(
            method=self._settings.embedding_elastic_submit_method,
            path=self._settings.embedding_elastic_submit_path,
            body={
                "documents": documents,
                "metadata": {
                    "chunk_count": len(documents),
                    "source": "ingest-orquestator-service",
                    "client": "elasticsearch",
                    "mapping_version": self._settings.embedding_elastic_mapping_version,
                },
            },
        )
        task_id = self._extract_field(response, self._settings.embedding_elastic_task_id_field)
        if not task_id:
            raise ElasticEmbeddingDispatchError(
                "Elastic embedding submit response did not include task id field "
                f"'{self._settings.embedding_elastic_task_id_field}'. Configure "
                "INGEST_EMBEDDING_ELASTIC_SUBMIT_PATH for an async endpoint that returns a task id."
            )

        return EmbeddingDispatchResult(
            task_id=str(task_id),
            accepted_document_count=len(documents),
            raw_response=response,
        )

    def get_task_status(self, task_id: str) -> EmbeddingTaskStatus:
        if task_id.startswith("elastic-bulk:"):
            response = {"completed": True, "task": task_id, "mode": "bulk"}
        else:
            response = self._get_remote_task_status(task_id)
        error = self._extract_task_error(response)
        return EmbeddingTaskStatus(
            task_id=task_id,
            completed=bool(response.get("completed")),
            failed=error is not None,
            error=error,
            raw_response=response,
        )

    def _chunk_documents(self, item: EmbeddingQueueItem) -> list[dict[str, Any]]:
        records = self._read_jsonl(
            item.embedding_input_path,
            include_local_paths=self._settings.embedding_elastic_include_local_paths,
        )
        return [self._chunk_document(item, record) for record in records]

    def _chunk_document(self, item: EmbeddingQueueItem, record: dict[str, Any]) -> dict[str, Any]:
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

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
        if self._uses_semantic_text_mapping:
            document["content_semantic"] = content
            document["title_semantic"] = title
        return document

    def _submit_bulk(self, documents: list[dict[str, Any]]) -> EmbeddingDispatchResult:
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
            task_id=self._bulk_task_id(documents),
            accepted_document_count=int(successful),
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
        if self._settings.embedding_elastic_pipeline and not self._uses_semantic_text_mapping:
            action["pipeline"] = self._settings.embedding_elastic_pipeline
        return action

    @property
    def _uses_semantic_text_mapping(self) -> bool:
        return self._settings.embedding_elastic_mapping_version == "v2"

    def _get_remote_task_status(self, task_id: str) -> dict[str, Any]:
        if self._settings.embedding_elastic_task_status_path_template == "/_tasks/{task_id}":
            try:
                response = (
                    self._elastic_client()
                    .options(
                        request_timeout=self._settings.embedding_elastic_request_timeout_seconds
                    )
                    .tasks.get(task_id=task_id)
                )
            except TransportError as exc:
                raise ElasticEmbeddingDispatchError(
                    f"Elastic task status request failed: {self._safe_exception_message(exc)}"
                ) from exc
            return self._response_to_dict(response)
        return self._perform_request(
            method="GET",
            path=self._settings.embedding_elastic_task_status_path_template.format(task_id=task_id),
        )

    def _perform_request(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = (
                self._elastic_client()
                .options(request_timeout=self._settings.embedding_elastic_request_timeout_seconds)
                .perform_request(
                    method,
                    path,
                    body=body,
                )
            )
        except TransportError as exc:
            raise ElasticEmbeddingDispatchError(
                f"Elastic request failed: {self._safe_exception_message(exc)}"
            ) from exc
        return self._response_to_dict(response)

    def _elastic_client(self) -> Elasticsearch:
        if self._client is not None:
            return self._client
        if self._settings.embedding_elastic_url is None:
            raise ElasticEmbeddingDispatchError(
                "INGEST_EMBEDDING_ELASTIC_URL must be configured when embedding queue is enabled."
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

    @staticmethod
    def _read_jsonl(path: Path, *, include_local_paths: bool) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if stripped:
                    record = json.loads(stripped)
                    if not include_local_paths and isinstance(record, dict):
                        metadata = record.get("metadata")
                        if isinstance(metadata, dict):
                            metadata.pop("source_path", None)
                    records.append(record)
        return records

    @staticmethod
    def _extract_field(payload: dict[str, Any], dotted_path: str) -> Any:
        current: Any = payload
        for part in dotted_path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    @staticmethod
    def _extract_task_error(payload: dict[str, Any]) -> str | None:
        if "error" in payload:
            return str(payload["error"])
        task = payload.get("task")
        if isinstance(task, dict):
            status = task.get("status")
            if isinstance(status, dict) and status.get("failures"):
                return str(status["failures"])
        return None

    @staticmethod
    def _bulk_task_id(documents: list[dict[str, Any]]) -> str:
        record_ids = ",".join(sorted(str(document["record_id"]) for document in documents))
        digest = sha256(record_ids.encode()).hexdigest()[:16]
        return f"elastic-bulk:{digest}"

    @staticmethod
    def _response_to_dict(response: Any) -> dict[str, Any]:
        body = getattr(response, "body", response)
        if isinstance(body, dict):
            return dict(body)
        return dict(body)

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
