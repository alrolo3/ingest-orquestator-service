import importlib
import sys
import types

from ingest_orquestator_server.application.services.job_parse_coordinator import (
    ParseJobResult,
)


def test_parser_actor_requeues_retrying_job_at_queue_tail(monkeypatch) -> None:
    dramatiq_actors = _import_dramatiq_actors(monkeypatch)
    publisher = RecordingPublisher()

    monkeypatch.setattr(
        dramatiq_actors,
        "build_parser_worker_service",
        lambda: RetryingWorkerService(),
    )
    monkeypatch.setattr(
        dramatiq_actors,
        "build_dramatiq_publisher",
        lambda _settings: publisher,
    )

    dramatiq_actors._process_parser_job("job-1")

    assert publisher.parser_job_ids == ["job-1"]


def _import_dramatiq_actors(monkeypatch):
    fake_dramatiq = types.ModuleType("dramatiq")
    fake_dramatiq.actor = lambda **_options: lambda fn: fn
    fake_dramatiq.set_broker = lambda _broker: None

    fake_brokers = types.ModuleType("dramatiq.brokers")
    fake_rabbitmq = types.ModuleType("dramatiq.brokers.rabbitmq")
    fake_rabbitmq.RabbitmqBroker = lambda **_kwargs: object()

    monkeypatch.setitem(sys.modules, "dramatiq", fake_dramatiq)
    monkeypatch.setitem(sys.modules, "dramatiq.brokers", fake_brokers)
    monkeypatch.setitem(sys.modules, "dramatiq.brokers.rabbitmq", fake_rabbitmq)

    return importlib.import_module(
        "ingest_orquestator_server.infrastructure.queue.dramatiq_actors"
    )


class RetryingWorkerService:
    def process_job(self, job_id: str) -> ParseJobResult:
        assert job_id == "job-1"
        return ParseJobResult(retry_requested=True)


class RecordingPublisher:
    def __init__(self) -> None:
        self.parser_job_ids: list[str] = []

    def enqueue_parser_job(self, job_id: str) -> None:
        self.parser_job_ids.append(job_id)
