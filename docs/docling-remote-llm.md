# Docling RemoteLLM Playbook

RemoteLLM is the service abstraction for Docling VLM calls that are served by
an external OpenAI-compatible chat completions endpoint. The API server no
longer loads vLLM in-process; vLLM, LM Studio, Ollama, or another compatible
runtime should run as a separate inference service.

Official Docling references:

- https://docling-project.github.io/docling/usage/gpu/#start-the-inference-server
- https://docling-project.github.io/docling/reference/pipeline_options/
- https://docling-project.github.io/docling/reference/document_converter/

## Runtime Boundary

Docling's VLM pipeline supports remote services through `VlmPipelineOptions`
with `enable_remote_services=True` and `ApiVlmOptions`-style configuration:
`url`, `params`, `concurrency`, `prompt`, and `timeout`.

This project maps that to:

```text
INGEST_DOCLING_REMOTE_LLM_URL=http://localhost:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_REMOTE_LLM_CONCURRENCY=2
```

RemoteLLM request concurrency follows `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY`.
Parser processes still call this remote endpoint; they do not load a local VLM.

## Start An External vLLM Server

Run this in a separate inference-server environment on the GPU host:

```bash
python3.12 -m venv .venv-vllm
source .venv-vllm/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-vllm.txt

vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --max-num-seqs 64 \
  --max-num-batched-tokens 8192 \
  --enable-chunked-prefill \
  --gpu-memory-utilization 0.9 \
  --trust-remote-code
```

Tune the vLLM server flags for the specific model and GPU. The API service only
needs the HTTP endpoint URL and served model id.

## Configure The API Service

Put these values in `.env`:

```text
INGEST_DOCLING_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_REMOTE_LLM_URL=http://127.0.0.1:8000/v1/chat/completions
INGEST_DOCLING_REMOTE_LLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
INGEST_DOCLING_REMOTE_LLM_CONCURRENCY=2
INGEST_DOCLING_REMOTE_LLM_PAGE_BATCH_SIZE=
INGEST_DOCLING_REMOTE_LLM_MAX_TOKENS=4096
INGEST_DOCLING_REMOTE_LLM_TEMPERATURE=0
INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_ENABLED=true
```

Standard-pipeline picture descriptions use the same VLM model and RemoteLLM
endpoint. Their token budget is the backend constant `2048`.

Docling recommends setting its page batch size at least as high as remote VLM
concurrency. The service uses `INGEST_DOCLING_REMOTE_LLM_CONCURRENCY` as the
page batch-size floor when `INGEST_DOCLING_REMOTE_LLM_PAGE_BATCH_SIZE` is unset.

## Health Checks

Manual check:

```bash
curl http://127.0.0.1:8000/health/remote-llm
```

Startup validation is disabled by default. Enable it when the API server should
fail fast if the RemoteLLM endpoint is not reachable:

```text
INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_ENABLED=true
INGEST_DOCLING_REMOTE_LLM_HEALTH_CHECK_TIMEOUT_SECONDS=5
```

The health check sends a minimal OpenAI-compatible chat completion request and
does not log API keys.

## Smoke Tests

Full-page VLM:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=vlm" \
  -F "file=@sample-inputs/sample.pdf")
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Standard pipeline with RemoteLLM picture descriptions:

```bash
response=$(curl -s -X POST "http://127.0.0.1:8000/v1/ingest/file?pipeline=standard" \
  -F "file=@sample-inputs/qwen3-picture-description-smoke.pdf")
job_id=$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"$response")
curl "http://127.0.0.1:8000/v1/ingest/jobs/${job_id}"
```

Inspect runtime metadata:

```bash
python - <<'PY'
import json
from pathlib import Path

latest = max(Path(".data/outputs").iterdir(), key=lambda p: p.stat().st_mtime)
manifest = json.loads((latest / "manifest.json").read_text())
print(json.dumps(manifest["diagnostics"]["metadata"]["runtime"], indent=2))
PY
```

Expected RemoteLLM markers include `resolved_runtime: remote_llm`, `mode:
remote`, and `remote_llm.url`.
