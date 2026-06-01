import os

import pytest

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_model_options import (
    build_picture_description_options,
    build_vlm_convert_options,
)
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)

pytestmark = pytest.mark.gpu


def _gpu_tests_enabled() -> bool:
    return os.environ.get("INGEST_GPU_TESTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


@pytest.mark.skipif(not _gpu_tests_enabled(), reason="set INGEST_GPU_TESTS=true")
def test_remote_llm_docling_options_build() -> None:
    settings = Settings(
        docling_vlm_model="granite_vision",
        docling_remote_llm_url="http://localhost:8000/v1/chat/completions",
        docling_remote_llm_concurrency=8,
    )

    vlm_resolution = resolve_vlm_convert_runtime(settings)
    picture_resolution = resolve_picture_description_runtime(settings)
    vlm_options = build_vlm_convert_options(settings)
    picture_options = build_picture_description_options(settings)

    assert vlm_resolution.resolved_runtime == "remote_llm"
    assert picture_resolution.resolved_runtime == "remote_llm"
    assert vlm_options.url == "http://localhost:8000/v1/chat/completions"
    assert picture_options.url == "http://localhost:8000/v1/chat/completions"
    assert vlm_options.concurrency == 8
    assert picture_options.concurrency == 8
