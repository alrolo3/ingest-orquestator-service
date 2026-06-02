from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_SERVICES = {"rabbitmq", "api", "parser-worker", "dispatch-worker", "frontend"}
RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/%2F"


def load_compose(name: str) -> dict[str, Any]:
    with (ROOT / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def service_environment(service: dict[str, Any]) -> dict[str, str]:
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return {str(key): str(value) for key, value in environment.items()}
    return dict(item.split("=", 1) for item in environment)


def command_contains_queue(service: dict[str, Any], queue_name: str) -> bool:
    command = service.get("command", [])
    return "--queues" in command and queue_name in command


def gpu_device_reservations(service: dict[str, Any]) -> list[dict[str, Any]]:
    return (
        service.get("deploy", {})
        .get("resources", {})
        .get("reservations", {})
        .get("devices", [])
    )


def assert_common_platform(
    compose: dict[str, Any],
    *,
    env_file: str,
    backend_dockerfile: str,
) -> None:
    services = compose["services"]
    assert PLATFORM_SERVICES <= services.keys()

    rabbitmq = services["rabbitmq"]
    assert rabbitmq["image"] == "rabbitmq:3.13-management"
    assert "rabbitmq-data:/var/lib/rabbitmq" in rabbitmq["volumes"]
    assert "${INGEST_RABBITMQ_BIND:-127.0.0.1}:${INGEST_RABBITMQ_PORT:-5672}:5672" in rabbitmq[
        "ports"
    ]

    api = services["api"]
    assert api["build"]["dockerfile"] == backend_dockerfile
    assert api["env_file"] == [env_file]
    assert "${INGEST_API_BIND:-127.0.0.1}:${INGEST_API_PORT:-8000}:8000" in api["ports"]

    api_environment = service_environment(api)
    assert api_environment["INGEST_QUEUE_BACKEND"] == "dramatiq"
    assert api_environment["INGEST_RABBITMQ_URL"] == RABBITMQ_URL
    assert api_environment["INGEST_STORAGE_DIR"] == "/app/.data"

    parser_worker = services["parser-worker"]
    assert parser_worker["build"]["dockerfile"] == backend_dockerfile
    assert parser_worker["env_file"] == [env_file]
    assert command_contains_queue(parser_worker, "ingest_parser_jobs")

    parser_environment = service_environment(parser_worker)
    assert parser_environment["INGEST_QUEUE_BACKEND"] == "dramatiq"
    assert parser_environment["INGEST_RABBITMQ_URL"] == RABBITMQ_URL
    assert parser_environment["INGEST_STORAGE_DIR"] == "/app/.data"

    dispatch_worker = services["dispatch-worker"]
    assert dispatch_worker["build"]["dockerfile"] == backend_dockerfile
    assert dispatch_worker["env_file"] == [env_file]
    assert command_contains_queue(dispatch_worker, "ingest_dispatch_jobs")

    frontend = services["frontend"]
    assert frontend["build"]["context"] == "./src/frontend"
    assert frontend["build"]["dockerfile"] == "Dockerfile"
    assert "${INGEST_FRONTEND_BIND:-0.0.0.0}:${INGEST_FRONTEND_PORT:-5173}:80" in frontend[
        "ports"
    ]
    assert frontend["depends_on"]["api"]["condition"] == "service_healthy"


def test_cpu_platform_compose_runs_the_full_stack() -> None:
    compose = load_compose("docker-compose.cpu.yml")

    assert_common_platform(compose, env_file="env-cpu", backend_dockerfile="Dockerfile")
    services = compose["services"]
    assert service_environment(services["api"])["INGEST_DOCLING_ACCELERATOR_DEVICE"] == "cpu"
    assert gpu_device_reservations(services["api"]) == []
    assert gpu_device_reservations(services["parser-worker"]) == []


def test_nvidia_gpu_platform_compose_runs_parser_on_gpu() -> None:
    compose = load_compose("docker-compose.nvidia-gpu.yml")

    assert_common_platform(compose, env_file="env-cuda-gpu", backend_dockerfile="Dockerfile.gpu")
    services = compose["services"]
    assert service_environment(services["api"])["INGEST_DOCLING_ACCELERATOR_DEVICE"] == "cuda"

    parser_devices = gpu_device_reservations(services["parser-worker"])
    assert parser_devices == [
        {"driver": "nvidia", "count": "all", "capabilities": ["gpu"]},
    ]
    assert gpu_device_reservations(services["api"]) == []
    assert gpu_device_reservations(services["dispatch-worker"]) == []


def test_frontend_container_proxies_api_requests() -> None:
    dockerfile = ROOT / "src/frontend/Dockerfile"
    nginx_config = ROOT / "src/frontend/nginx.conf"
    dockerignore = ROOT / "src/frontend/.dockerignore"

    assert dockerfile.exists()
    assert nginx_config.exists()
    assert dockerignore.exists()

    dockerfile_text = dockerfile.read_text(encoding="utf-8")
    assert "npm ci" in dockerfile_text
    assert "nginx:" in dockerfile_text

    nginx_text = nginx_config.read_text(encoding="utf-8")
    assert "location /v1/" in nginx_text
    assert "location /health" in nginx_text
    assert "proxy_pass http://api:8000" in nginx_text
