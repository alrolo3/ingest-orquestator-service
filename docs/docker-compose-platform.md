# Docker Compose Platform Deployment

## Objective

Run the complete ingest platform with one Docker Compose command: RabbitMQ,
FastAPI, parser worker, dispatch worker, and the production frontend.

## Commands

CPU:

```bash
docker compose -f docker-compose.cpu.yml up --build
```

NVIDIA GPU:

```bash
docker compose -f docker-compose.nvidia-gpu.yml up --build
```

Open the frontend:

```text
http://127.0.0.1:5173
```

The API is still reachable from the Docker host at:

```text
http://127.0.0.1:8000
```

RabbitMQ management is available on the Docker host at:

```text
http://127.0.0.1:15672
```

## Project Structure

- `docker-compose.cpu.yml`: full CPU stack.
- `docker-compose.nvidia-gpu.yml`: full NVIDIA GPU stack.
- `Dockerfile`: CPU backend/API/worker image.
- `Dockerfile.gpu`: CUDA backend/API/worker image.
- `src/frontend/Dockerfile`: production frontend image.
- `src/frontend/nginx.conf`: static frontend server and same-origin API proxy.
- `env-cpu`: source-safe CPU environment values.
- `env-cuda-gpu`: source-safe GPU environment values.

## Runtime Design

The API and workers run with `INGEST_QUEUE_BACKEND=dramatiq`, so uploads return
queued jobs and parsing is handled by `parser-worker`. Parsed document dispatch
is handled by `dispatch-worker`. All backend services share `./.data` at
`/app/.data` so uploads, SQLite state, and generated artifacts are visible
across the API and workers.

The frontend is served by nginx. Browser API calls default to same-origin
`/v1/...` and `/health`; nginx proxies those requests to the internal Compose
service `api:8000`. This avoids baking a specific host IP into the frontend
image and works from local or remote browsers.

The GPU compose reserves NVIDIA devices only for `parser-worker`. The API and
dispatch worker use the GPU environment for consistent capability metadata, but
do not reserve GPU devices so parsing has priority.

## Configuration

The compose files expose conservative defaults:

- Frontend: `0.0.0.0:5173`
- API: `127.0.0.1:8000`
- RabbitMQ AMQP: `127.0.0.1:5672`
- RabbitMQ management: `127.0.0.1:15672`

Override bindings and ports with environment variables:

```bash
INGEST_FRONTEND_PORT=8080 docker compose -f docker-compose.cpu.yml up --build
INGEST_API_BIND=0.0.0.0 docker compose -f docker-compose.cpu.yml up --build
```

On GPU hosts, mount the model cache used by the checked-in env files:

```bash
INGEST_HOST_MODELS_DIR=/datastore/models \
  docker compose -f docker-compose.nvidia-gpu.yml up --build
```

To select a specific GPU:

```bash
NVIDIA_VISIBLE_DEVICES=0 docker compose -f docker-compose.nvidia-gpu.yml up --build
```

## Smoke Test

After the stack is healthy, submit a small sample through the same endpoint used
by the frontend:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@sample-inputs/sample.md")
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}" | python -m json.tool
```

## Boundaries

- Always: keep secrets in local env files or runtime environment variables.
- Always: keep RabbitMQ and API bound to loopback unless they must be exposed.
- Ask first: adding Elasticsearch, RemoteLLM, or other external services to the
  default platform compose.
- Never: commit real Elastic credentials, RemoteLLM keys, or private model
  tokens.

## Migration Notes

The older compose files remain available for focused workflows:

- `docker-compose.yml`: backend API only.
- `docker-compose.gpu.yml`: GPU override for the backend-only compose.
- `docker-compose-queues.yml`: queue workers and RabbitMQ only.
- `docker-compose-rabbitmq.yml`: RabbitMQ only.

For normal platform deployment, prefer `docker-compose.cpu.yml` or
`docker-compose.nvidia-gpu.yml`.
