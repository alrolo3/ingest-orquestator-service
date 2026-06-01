from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.queue.dramatiq_runtime import (
    dispatch_actor_options,
    parser_actor_options,
)


def test_dramatiq_actor_options_use_configured_time_limits() -> None:
    settings = Settings(
        dramatiq_parser_queue_name="parser-custom",
        dramatiq_dispatch_queue_name="dispatch-custom",
        dramatiq_parser_time_limit_ms=1234,
        dramatiq_dispatch_time_limit_ms=5678,
    )

    assert parser_actor_options(settings) == {
        "queue_name": "parser-custom",
        "time_limit": 1234,
    }
    assert dispatch_actor_options(settings) == {
        "queue_name": "dispatch-custom",
        "time_limit": 5678,
    }
