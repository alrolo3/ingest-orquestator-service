# Frontend App

The v2.0 MVP frontend is an independent Node app under `src/frontend`. It runs
beside the FastAPI service and uses the public ingestion API only.

## Requirements

- Node.js 20 or newer.
- The FastAPI server running on the configured API URL.
- Browser access to the API origin. In Docker Compose, nginx proxies API
  traffic through the frontend origin. In Vite development, the dev server
  proxies `/v1` and `/health` to `http://127.0.0.1:8000`.

## Install

```bash
cd src/frontend
npm install
```

## Run

Start the API server from the repository root:

```bash
source .venv/bin/activate
python -m uvicorn ingest_orquestator_server.main:app --host 0.0.0.0 --port 8000
```

Start the frontend in another terminal:

```bash
cd src/frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The frontend API base URL defaults to same-origin requests. Override it when
you intentionally want the browser to call another API origin directly:

```bash
cd src/frontend
VITE_INGEST_API_BASE_URL=http://192.168.30.20:8000 npm run dev
```

## Workflow

1. Select or drag one or more files.
2. Choose parser, pipeline, chunking, and compatibility options.
3. Submit the upload.
4. Monitor one job per file through parser and dispatch phases.
5. Open completed metadata, confidence summary, and output artifact links.

The app polls `GET /v1/ingest/jobs/{job_id}` for active jobs. It stops polling
when a job reaches `completed` or `failed`.

## Build And Test

```bash
cd src/frontend
npm run lint
npm test
npm run build
```

`npm run lint` is a TypeScript no-emit check. The test suite uses mocked API
responses, so it does not require Docling, GPU models, or a running API server.

Run the optional browser smoke test only when the API server is already running:

```bash
cd src/frontend
npx playwright install chromium
RUN_FRONTEND_E2E=true VITE_INGEST_API_BASE_URL=http://127.0.0.1:8000 npm run test:e2e
```

## API Integration

The frontend reads UI-safe option metadata from:

```http
GET /v1/ingest/capabilities
```

It uploads through:

```http
POST /v1/ingest/file
POST /v1/ingest/files
```

It retrieves completed output links through:

```http
GET /v1/ingest/jobs/{job_id}/outputs/{output_type}
```

## Configuration

Set API CORS origins in the backend `.env`:

```bash
INGEST_CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

For a remote GPU server frontend session, add the browser origin you will use:

```bash
INGEST_CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://GPU_HOST:5173
```

Do not put Elasticsearch credentials or RemoteLLM keys in frontend env files.
The frontend only needs the ingestion API base URL.

## Docker Compose

The full platform compose files build and serve the production frontend through
nginx:

```bash
docker compose -f docker-compose.cpu.yml up --build
docker compose -f docker-compose.nvidia-gpu.yml up --build
```

Open:

```text
http://127.0.0.1:5173
```

See [docker-compose-platform.md](docker-compose-platform.md) for deployment
ports and smoke-test commands.
