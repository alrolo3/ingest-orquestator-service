import importlib
import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor

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


def test_parser_actor_limits_concurrent_jobs_to_parser_worker_count(monkeypatch) -> None:
    dramatiq_actors = _import_dramatiq_actors(monkeypatch)
    worker = BlockingWorkerService()

    monkeypatch.setattr(dramatiq_actors, "_parser_actor_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(
        dramatiq_actors,
        "build_parser_worker_service",
        lambda: worker,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(dramatiq_actors._process_parser_job, "job-1")
        assert worker.first_started.wait(timeout=1)
        second = executor.submit(dramatiq_actors._process_parser_job, "job-2")
        assert not worker.second_started.wait(timeout=0.05)
        worker.release.set()
        first.result(timeout=1)
        second.result(timeout=1)

    assert worker.max_active == 1
    assert worker.job_ids == ["job-1", "job-2"]


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


class BlockingWorkerService:
    def __init__(self) -> None:
        self.first_started = threading.Event()
        self.second_started = threading.Event()
        self.release = threading.Event()
        self.active = 0
        self.max_active = 0
        self.job_ids: list[str] = []
        self.lock = threading.Lock()

    def process_job(self, job_id: str) -> ParseJobResult:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.job_ids.append(job_id)
            if len(self.job_ids) == 1:
                self.first_started.set()
            if len(self.job_ids) == 2:
                self.second_started.set()
        try:
            self.release.wait(timeout=1)
            return ParseJobResult()
        finally:
            with self.lock:
                self.active -= 1
