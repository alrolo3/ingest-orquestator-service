import pytest

from ingest_orquestator_server.application.services.job_parse_coordinator import (
    ParseJobResult,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.queue import dramatiq_runtime


def test_dramatiq_actor_options_use_configured_time_limits() -> None:
    settings = Settings(
        dramatiq_parser_queue_name="parser-custom",
        dramatiq_dispatch_queue_name="dispatch-custom",
        dramatiq_parser_time_limit_ms=1234,
        dramatiq_dispatch_time_limit_ms=5678,
    )

    assert dramatiq_runtime.parser_actor_options(settings) == {
        "queue_name": "parser-custom",
        "time_limit": 1234,
    }
    assert dramatiq_runtime.dispatch_actor_options(settings) == {
        "queue_name": "dispatch-custom",
        "time_limit": 5678,
    }


def test_run_parser_job_builds_process_local_coordinator_from_settings_snapshot(
    monkeypatch,
) -> None:
    seen_settings: list[Settings] = []

    class RecordingCoordinator:
        def process_job(self, job_id: str, **kwargs) -> ParseJobResult:
            assert job_id == "job-1"
            assert kwargs == {
                "preserve_existing_started_at": True,
                "fail_missing_input_before_start": True,
            }
            return ParseJobResult()

    def build_coordinator(settings: Settings):
        seen_settings.append(settings)
        return RecordingCoordinator()

    monkeypatch.setattr(
        dramatiq_runtime,
        "build_parser_job_coordinator",
        build_coordinator,
    )

    result = dramatiq_runtime.run_parser_job(
        "job-1",
        Settings(parser_process_count=5, parser_threads_per_process=2).model_dump(
            mode="python"
        ),
    )

    assert result.retry_requested is False
    assert seen_settings[0].parser_process_count == 5
    assert seen_settings[0].parser_threads_per_process == 2


def test_run_parser_job_in_subprocess_uses_spawned_child_process(monkeypatch) -> None:
    context = FakeProcessContext()
    seen_jobs: list[tuple[str, int, int]] = []

    def get_context(method: str) -> FakeProcessContext:
        context.method = method
        return context

    def run_parser_job(job_id: str, settings_data: dict) -> ParseJobResult:
        settings = Settings(**settings_data)
        seen_jobs.append(
            (
                job_id,
                settings.parser_process_count,
                settings.parser_threads_per_process,
            )
        )
        return ParseJobResult(retry_requested=True)

    monkeypatch.setattr(dramatiq_runtime, "get_context", get_context)
    monkeypatch.setattr(dramatiq_runtime, "run_parser_job", run_parser_job)

    result = dramatiq_runtime.run_parser_job_in_subprocess(
        "job-1",
        Settings(parser_process_count=3, parser_threads_per_process=1).model_dump(
            mode="python"
        ),
    )

    assert result.retry_requested is True
    assert context.method == "spawn"
    assert context.process_names == ["ingest-parser-job-job-1"]
    assert seen_jobs == [("job-1", 3, 1)]


def test_run_parser_job_in_subprocess_surfaces_child_failures(monkeypatch) -> None:
    context = FakeProcessContext()

    monkeypatch.setattr(dramatiq_runtime, "get_context", lambda _method: context)

    def run_parser_job(_job_id: str, _settings_data: dict) -> ParseJobResult:
        raise ValueError("parse failed")

    monkeypatch.setattr(dramatiq_runtime, "run_parser_job", run_parser_job)

    with pytest.raises(RuntimeError, match="ValueError: parse failed"):
        dramatiq_runtime.run_parser_job_in_subprocess(
            "job-1",
            Settings().model_dump(mode="python"),
        )


class FakeProcessContext:
    def __init__(self) -> None:
        self.method: str | None = None
        self.messages: list[tuple] = []
        self.process_names: list[str] = []

    def Pipe(self, *, duplex: bool):
        assert duplex is False
        return FakeReadConnection(self.messages), FakeWriteConnection(self.messages)

    def Process(self, *, target, args: tuple, name: str):
        self.process_names.append(name)
        return FakeProcess(target, args)


class FakeProcess:
    def __init__(self, target, args: tuple) -> None:
        self._target = target
        self._args = args
        self._alive = False
        self.exitcode: int | None = None
        self.terminated = False
        self.killed = False

    def start(self) -> None:
        self._alive = True
        try:
            self._target(*self._args)
        except BaseException:
            self.exitcode = 1
        else:
            self.exitcode = 0
        finally:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False

    def kill(self) -> None:
        self.killed = True
        self._alive = False


class FakeReadConnection:
    def __init__(self, messages: list[tuple]) -> None:
        self._messages = messages

    def poll(self) -> bool:
        return bool(self._messages)

    def recv(self) -> tuple:
        return self._messages.pop(0)

    def close(self) -> None:
        return None


class FakeWriteConnection:
    def __init__(self, messages: list[tuple]) -> None:
        self._messages = messages

    def send(self, message: tuple) -> None:
        self._messages.append(message)

    def close(self) -> None:
        return None
