# Queue System Rework

## Objective
Support asynchronous file ingestion through a queue backend that can use RabbitMQ and
dramatiq while keeping the existing local development flow working. Upload routes create
jobs and return queued responses; application services own parsing, normalization, and
dispatch orchestration.

## Current Boundaries
- Routes validate HTTP concerns and delegate to application services.
- `FileIngestionService` creates persisted `IngestionJob` records.
- `ParserWorkerService` executes parser jobs through `JobParseCoordinator`.
- `DocumentParseService` selects a `DocumentParser` and normalizes parser output.
- `EmbeddingDispatchService` owns output handoff to local storage and Elasticsearch.

## Queue Contract
- Parser queue messages contain the persisted `job_id`.
- Dispatch queue messages contain a serialized output queue item with the normalized
  document payload needed by an independent dispatcher worker.
- Queue publishers are application ports; RabbitMQ/dramatiq is an infrastructure adapter.
- Dramatiq actors stay thin and call existing application services.

## Compatibility
- `local` queue backend keeps current in-process behavior for tests and local runs.
- `dramatiq` queue backend publishes parser and dispatch messages to dramatiq actors.
- Existing upload API paths and response models are unchanged.

## Validation
- Unit tests cover queue publisher wiring without requiring a live RabbitMQ broker.
- Existing parser and dispatch flow tests continue to exercise the local backend.
