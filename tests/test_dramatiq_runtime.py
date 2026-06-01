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
