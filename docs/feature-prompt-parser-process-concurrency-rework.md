$using-agent-skills
$spec-driven-development
$test-driven-development
$code-review-and-quality
$code-simplification
$planning-and-task-breakdown
$deprecation-and-migration
$security-and-hardening
$performance-optimization

Use Serena for repository navigation, symbol search, reference analysis, and safe code edits.

Feature x):
Redesign parser concurrency so each document parse workflow runs in an independent process instead of being limited by an in-process thread pool.

The current parser worker model uses a thread pool with `N` workers. Each worker processes one document, but the document parse itself does not fully use the parser engine concurrency capabilities. This was originally intentional because the service had a low memory footprint requirement for GPU and CPU deployments, and shared parser or model instances were preferred.

That memory restriction is no longer the primary design constraint. As the number of documents and document sizes increase, the service must support higher throughput and better isolation per parse job.

The parser worker pool must be reworked from thread-oriented concurrency to process-oriented concurrency:

- Each queued parse workflow, from job intake to successful enqueue into the dispatch queue, must execute in an independent process.
- A parser process may use the parser engine's own internal concurrency for that single document.
- For Docling, it is mandatory to enable and preserve Docling's own multithreading or pipeline-stage concurrency for the document being parsed.
- Do not preserve the previous restriction that parser workers must share a single local LLM or local model instance.
- Each parser process may create the parser/model/runtime instances it needs to satisfy the configured concurrency level.
- VLM/image-description usage must remain compatible with the existing remote-LLM design. Do not introduce mandatory local VLM loading.
- The queue architecture must remain safe for RabbitMQ/Dramatiq ack semantics, retries, cancellation, observability, and status tracking.

Relevant references to investigate before editing:

- Local official reference implementation under `src/docling-serve`.
- Docling GPU documentation: `https://docling-project.github.io/docling/usage/gpu/`
- Docling concurrency discussion: `https://github.com/docling-project/docling/issues/115`
- Docling Serve repository: `https://github.com/docling-project/docling-serve`

Goals:

1. Replace parser document concurrency based on worker threads with parser document concurrency based on worker processes.
2. Keep queue-level concurrency explicit and predictable.
3. Allow each parser process to use Docling's internal concurrency for a single document.
4. Avoid shared mutable parser/runtime state across parse processes.
5. Keep the dispatch queue contract unchanged unless a change is explicitly required by the new process model.
6. Make worker status and metrics distinguish configured process concurrency from active parsing jobs, reserved/unacked queue messages, and queued jobs.
7. Preserve current API behavior and public contracts unless the plan explicitly identifies a necessary migration.

Non-goals:

- Do not redesign the entire ingestion domain model.
- Do not replace RabbitMQ/Dramatiq unless the audit proves it cannot support the required model.
- Do not add local VLM loading as a mandatory runtime mode.
- Do not introduce a frontend redesign unless existing queue metrics become incorrect and need UI wording or count fixes.
- Do not hide process concurrency behind ambiguous names like `worker_count` without documenting what it means.

Expected design direction:

- Prefer running Dramatiq parser workers with multiple processes and one thread per process, for example:

```bash
python -m dramatiq ingest_orquestator_server.infrastructure.queue.dramatiq_actors \
  --processes "${INGEST_PARSER_PROCESS_COUNT:-2}" \
  --threads "${INGEST_PARSER_THREADS_PER_PROCESS:-1}" \
  --queues ingest_parser_jobs
```

- Keep dispatch workers independently configurable, for example:

```bash
python -m dramatiq ingest_orquestator_server.infrastructure.queue.dramatiq_actors \
  --processes "${INGEST_DISPATCH_PROCESS_COUNT:-1}" \
  --threads "${INGEST_DISPATCH_THREADS_PER_PROCESS:-2}" \
  --queues ingest_dispatch_jobs
```

- If the current `INGEST_PARSER_WORKER_COUNT` is retained temporarily, treat it as deprecated or migrate it clearly:
  - Either map it to `INGEST_PARSER_PROCESS_COUNT` with warnings and documentation.
  - Or keep it only as a backwards-compatible alias.
  - Do not silently change its meaning without tests and docs.

- Docling parser initialization should be process-local.
- Docling internal concurrency should be configured through explicit settings, not accidental defaults.
- The service must avoid building one global parser engine in the parent process and then forking it into children.
- Queue status should not report "8 parser workers" when the actual configured parse process count is 4. UI/API naming must separate:
  - configured parser processes
  - active parser jobs
  - queued parser messages
  - unacknowledged/reserved parser messages
  - stale parsing jobs

First:

1. Use Serena to map the current flow related to parser concurrency:
   - API upload and enqueue path
   - parser queue actor
   - parser worker service
   - Docling parser construction and lifecycle
   - job status transitions
   - dispatch queue enqueue
   - queue metrics and frontend status display
2. Identify affected modules, classes, functions, and references.
3. Compare the current implementation with `src/docling-serve` and identify which concurrency ideas are relevant for this service.
4. Propose a short plan before editing.
5. List the required tests before editing.
6. Make sure the plan is clear before editing.

Required audit questions:

1. Where is the parser engine instantiated?
2. Is any parser, Docling converter, model, tokenizer, VLM client, or runtime object shared across jobs or across threads?
3. Does the current queue actor rely on thread-local assumptions?
4. Does Dramatiq prefetch or ack behavior allow more reserved jobs than active parser processes?
5. Can a long Docling job exceed the current Dramatiq time limit?
6. Are parser statuses recovered if a process dies?
7. Are stale `PARSING` jobs visible and recoverable?
8. Does the frontend display active jobs, workers, processes, or queued messages correctly?
9. Are settings names clear enough for GPU server operators?
10. Are docs and startup commands aligned with the real process model?

Then:

1. Implement the feature with focused, low-churn changes.
2. Add or update tests before finalizing the behavior.
3. Update docs and GPU startup commands.
4. Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

5. If frontend is touched, also run:

```bash
cd src/frontend && npm run lint
cd src/frontend && npm test
cd src/frontend && npm run build
```

6. Summarize:
   - files touched
   - what changed
   - tests added or modified
   - validations executed
   - remaining risks

Required tests:

1. Settings tests:
   - `INGEST_PARSER_PROCESS_COUNT` is parsed correctly.
   - `INGEST_PARSER_THREADS_PER_PROCESS` is parsed correctly.
   - legacy `INGEST_PARSER_WORKER_COUNT` behavior is explicit and documented.
   - invalid zero or negative process/thread values fail safely.

2. Queue actor tests:
   - parser actor processes one job and enqueues exactly one dispatch job on success.
   - parser actor leaves no shared parser runtime state between jobs.
   - parser actor records failure state on parser exceptions.
   - parser actor respects configured time limits.

3. Parser lifecycle tests:
   - Docling parser/converter is created process-local or job-local according to the selected design.
   - parser construction does not happen in the parent process before worker forking.
   - Docling internal concurrency options are passed from settings.

4. Status and metrics tests:
   - active parser job count is not confused with configured parser process count.
   - queued messages and unacknowledged messages are reported separately when the backend exposes them.
   - stale `PARSING` jobs can be detected or recovered according to existing lifecycle rules.

5. Dispatch contract tests:
   - parsed output format sent to the dispatch queue remains compatible.
   - dispatch queue receives the same job/document identifiers as before.
   - local and Elasticsearch sink behavior remains unchanged.

6. Regression tests:
   - existing synchronous or in-memory queue tests still pass.
   - CPU-only parsing still works.
   - remote-LLM/VLM image-description configuration remains remote and does not require local model loading.

Acceptance criteria:

1. Parser document concurrency is controlled by process count, not by a thread pool that shares parser runtime state.
2. Each parser process can use Docling's internal concurrency for its assigned document.
3. The service no longer assumes a single shared local LLM/model across parser workers.
4. VLM image description remains compatible with remote-LLM configuration.
5. RabbitMQ/Dramatiq commands for GPU servers are documented and copy-pastable.
6. Queue metrics and UI labels no longer imply that active parsing jobs equal configured worker capacity.
7. Tests prove settings, actor behavior, lifecycle, status accounting, and dispatch compatibility.
8. Backend validation passes with `pytest` and `ruff`.
9. Frontend validation passes if frontend files are touched.

Implementation notes:

- Treat this as a concurrency and lifecycle refactor, not only a command-line change.
- Be careful with fork safety. Avoid creating heavy parser/model objects before process fork.
- Keep process count conservative by default for GPU deployments.
- Make memory tradeoffs explicit in docs.
- Do not print secrets from `.env`.
- Do not commit local-only `.env`, `.serena`, `.codex`, `.agents`, or accidental scratch files.
- Prefer small characterization tests around current behavior before changing worker internals.
- If changing public setting names, document migration from the old environment variables.

