# Linux GPU RabbitMQ/Dramatiq Setup With Terminal API

This setup runs the FastAPI application from a normal terminal and runs
RabbitMQ plus the parser and dispatch Dramatiq workers with Docker Compose.

The API and worker containers share the repository `.data` directory. Run all
commands from the repository root so relative paths written by the API can be
read by the worker containers.

## 1. Verify The GPU Server

```bash
nvidia-smi
docker --version
docker compose version
```

If GPU containers are not configured yet, install the NVIDIA Container Toolkit
for the host distribution, then verify Docker can see the GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 2. Create The API Virtual Environment

```bash
cd /path/to/ingest-orquestator-service

sudo apt-get update
sudo apt-get install -y \
  python3.12 python3.12-venv python3.12-dev build-essential \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

Install a CUDA-enabled PyTorch build that matches the server. Use the official
PyTorch selector for the exact command for the installed driver/runtime, then
verify CUDA:

```bash
python - <<'PY'
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
PY
```

Continue only when `torch.cuda.is_available()` prints `True`.

Install the application:

```bash
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

## 3. Prepare The Runtime Environment

```bash
test -f .env || cp env-cuda-gpu .env
mkdir -p .data
```

For this deployment, the host API must talk to RabbitMQ through localhost:

```bash
export INGEST_QUEUE_BACKEND=dramatiq
export INGEST_RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
export INGEST_STORAGE_DIR=.data
```

If using an external RemoteLLM server from the host, avoid port `8000` because
the API uses that port. Use `8001` for the LLM server:

```bash
export INGEST_DOCLING_REMOTE_LLM_URL=http://127.0.0.1:8001/v1/chat/completions
```

The parser worker container reaches that same host service through
`host.docker.internal`. Set this in `.env` when RemoteLLM is enabled:

```bash
python - <<'PY'
from pathlib import Path

path = Path(".env")
lines = path.read_text().splitlines()
key = "INGEST_DOCLING_REMOTE_LLM_URL"
value = f"{key}=http://host.docker.internal:8001/v1/chat/completions"
for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[index] = value
        break
else:
    lines.append(value)
path.write_text("\n".join(lines) + "\n")
PY
```

## 4. Start RabbitMQ And Queue Workers

Build and start RabbitMQ, the parser worker, and the dispatch worker:

```bash
docker compose -f docker-compose-queues.yml up -d --build
```

Check status and logs:

```bash
docker compose -f docker-compose-queues.yml ps
docker compose -f docker-compose-queues.yml logs -f rabbitmq
docker compose -f docker-compose-queues.yml logs -f parser-worker
docker compose -f docker-compose-queues.yml logs -f dispatch-worker
```

RabbitMQ is bound to localhost on the GPU server:

```text
AMQP: http://127.0.0.1:5672
Management UI: http://127.0.0.1:15672
User/password: guest/guest
```

For a remote browser, use an SSH tunnel instead of exposing the management port:

```bash
ssh -L 15672:127.0.0.1:15672 user@gpu-server
```

## 5. Run The API From The Terminal

Open a separate terminal on the GPU server:

```bash
cd /path/to/ingest-orquestator-service
source .venv/bin/activate

set -a
source .env
set +a

export INGEST_QUEUE_BACKEND=dramatiq
export INGEST_RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
export INGEST_STORAGE_DIR=.data

python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

In this mode the API creates jobs and publishes them to RabbitMQ. The parser and
dispatch workers running in Compose consume the jobs.

## 6. Smoke Test The Full Flow

```bash
curl http://127.0.0.1:8000/health

printf "# GPU queue smoke test\n\nHello from the GPU server.\n" > /tmp/ingest-smoke.md

response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/tmp/ingest-smoke.md")
echo "$response"

job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Watch the worker logs while the job runs:

```bash
docker compose -f docker-compose-queues.yml logs -f parser-worker dispatch-worker
```

For a PDF:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@/path/to/document.pdf")
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Download outputs after completion:

```bash
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}/outputs/normalized"
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}/outputs/chunks"
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}/outputs/embedding"
```

## 7. Scale Worker Concurrency

For one GPU, keep parser actor threads at `1` and scale document throughput with
parser processes. Each parser process handles one queued parse workflow and can
use Docling's own threaded PDF pipeline stages for that document:

```bash
INGEST_PARSER_PROCESS_COUNT=2 INGEST_PARSER_THREADS_PER_PROCESS=1 \
INGEST_DISPATCH_WORKER_COUNT=2 \
  docker compose -f docker-compose-queues.yml up -d --build
```

The parser worker container runs Dramatiq with
`${INGEST_PARSER_PROCESS_COUNT:-2}` processes and
`${INGEST_PARSER_THREADS_PER_PROCESS:-1}` thread per process. More parser
processes improve isolation and document throughput but duplicate Docling engine
pools and increase memory use. RemoteLLM request concurrency is controlled
separately with `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY`.

The equivalent direct Dramatiq commands are:

```bash
python -m dramatiq ingest_orquestator_server.infrastructure.queue.dramatiq_actors \
  --processes "${INGEST_PARSER_PROCESS_COUNT:-2}" \
  --threads "${INGEST_PARSER_THREADS_PER_PROCESS:-1}" \
  --queues ingest_parser_jobs

python -m dramatiq ingest_orquestator_server.infrastructure.queue.dramatiq_actors \
  --processes 1 \
  --threads "${INGEST_DISPATCH_WORKER_COUNT:-2}" \
  --queues ingest_dispatch_jobs
```

Parser jobs use `INGEST_DRAMATIQ_PARSER_TIME_LIMIT_MS`; keep it above the
worst-case OCR duration for your largest PDFs so Dramatiq does not interrupt
Docling while its page-stage threads are active. Restart both the API process
that enqueues parser messages and the Dramatiq worker after changing this value.
Messages that were already queued keep their original Dramatiq options.
Parser failures are republished at the parser queue tail while
`INGEST_PARSER_MAX_RETRY_ATTEMPTS` has remaining budget; the job metadata records
the retry state and last parser error.

Dramatiq's CLI does not expose RabbitMQ prefetch in this version. RabbitMQ may
show reserved/unacknowledged messages separately from active parser jobs; the
API queue metrics therefore reports configured parser processes, active parser
jobs, queued parser jobs, and stale parsing jobs as separate values.

If GPU memory is tight, reduce parser processes in `.env`:

```text
INGEST_PARSER_PROCESS_COUNT=1
```

## 8. Stop Or Restart

Stop only the API with `Ctrl+C` in its terminal.

Stop RabbitMQ and workers:

```bash
docker compose -f docker-compose-queues.yml down
```

Keep RabbitMQ data but rebuild workers:

```bash
docker compose -f docker-compose-queues.yml up -d --build --force-recreate parser-worker dispatch-worker
```

Remove RabbitMQ persisted data:

```bash
docker compose -f docker-compose-queues.yml down -v
```

## Notes

- Keep `INGEST_STORAGE_DIR=.data` for both the terminal API and worker
  containers. This keeps persisted input and output paths portable between the
  host process and containers.
- The Compose file binds RabbitMQ ports to `127.0.0.1` on the GPU server.
  Expose them only through SSH tunnels or a private network.
- The current job repository is SQLite in `.data/jobs.sqlite3`. It works for a
  single GPU server, but a multi-node production deployment should move job
  state to a server database such as PostgreSQL.
