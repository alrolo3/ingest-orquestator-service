import pytest
from pydantic import ValidationError

from ingest_orquestator_server.config import Settings


def test_env_example_matches_cuda_gpu_env() -> None:
    with open(".env.example") as example_file, open("env-cuda-gpu") as cuda_file:
        assert example_file.read() == cuda_file.read()


def test_env_files_define_all_settings_keys() -> None:
    expected = {f"INGEST_{name.upper()}" for name in Settings.model_fields}

    for path in [".env.example", "env-cuda-gpu", "env-cpu"]:
        with open(path) as env_file:
            actual = {
                line.split("=", 1)[0].strip()
                for line in env_file
                if line.strip().startswith("INGEST_") and "=" in line
            }
        assert actual == expected


def test_settings_accept_cuda_device() -> None:
    settings = Settings(docling_accelerator_device="CUDA:1")

    assert settings.docling_accelerator_device == "cuda:1"


def test_settings_reject_unknown_accelerator_device() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_accelerator_device="gpu")


def test_settings_parse_allowed_upload_extensions_from_string() -> None:
    settings = Settings(allowed_upload_extensions=".PDF, md, .txt")

    assert settings.allowed_upload_extensions == [".md", ".pdf", ".txt"]


def test_env_example_loads() -> None:
    settings = Settings(_env_file=".env.example")

    assert settings.docling_pdf_ocr_engine == "suryaocr"
    assert settings.docling_pdf_ocr_languages == ["en"]
    assert settings.chunking_enabled is False
    assert settings.chunking_strategy == "page"
    assert (
        str(settings.chunk_tokenizer_path)
        == "/datastore/models/tokenizers/qwen3-embedding-8b"
    )
    assert settings.confidence_output_enabled is True
    assert settings.docling_accelerator_device == "cuda"
    assert settings.docling_xbrl_enable_local_fetch is True
    assert settings.docling_engine_cache_enabled is True
    assert settings.docling_engine_warmup_enabled is False
    assert settings.docling_engine_warmup_formats == ["pdf"]
    assert settings.parser_process_count == 2
    assert settings.parser_threads_per_process == 1
    assert settings.effective_docling_parse_concurrency == (
        settings.parser_threads_per_process
    )
    assert settings.docling_engine_idle_ttl_seconds == 0
    assert settings.docling_perf_page_batch_size == 32
    assert settings.docling_remote_llm_url == "http://localhost:8000/v1/chat/completions"
    assert settings.docling_remote_llm_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.docling_remote_llm_concurrency == 2
    assert settings.docling_pdf_picture_description_max_new_tokens == 2048
    assert settings.docling_remote_llm_page_batch_size is None
    assert settings.queue_backend == "local"
    assert settings.rabbitmq_url == "amqp://guest:guest@localhost:5672/%2F"
    assert settings.dramatiq_parser_queue_name == "ingest_parser_jobs"
    assert settings.dramatiq_dispatch_queue_name == "ingest_dispatch_jobs"
    assert settings.dramatiq_parser_time_limit_ms == 14_400_000
    assert settings.dramatiq_dispatch_time_limit_ms == 600_000
    assert settings.parser_max_retry_attempts == 3
    assert settings.parser_worker_count == settings.parser_process_count
    assert settings.dispatch_worker_count == 2
    assert settings.dispatch_queue_max_payload_bytes is None
    assert settings.dispatch_max_bulk_size == 5
    assert settings.dispatch_sink_mode == "local"
    assert settings.embedding_elastic_mapping_version == "v2"
    assert settings.embedding_elastic_index == "open-rag-embeddings-v2"
    assert settings.embedding_elastic_pipeline is None


def test_cuda_gpu_env_loads() -> None:
    settings = Settings(_env_file="env-cuda-gpu")

    assert settings.docling_accelerator_device == "cuda"
    assert settings.docling_num_threads == 32
    assert settings.docling_cuda_use_flash_attention2 is False
    assert settings.docling_pdf_ocr_use_gpu is True
    assert settings.docling_pdf_ocr_batch_size == 32
    assert settings.docling_pdf_layout_batch_size == 32
    assert settings.docling_pdf_table_batch_size == 32
    assert settings.docling_pdf_queue_max_size == 512
    assert settings.chunk_max_tokens == 1024
    assert settings.docling_xbrl_enable_local_fetch is True
    assert settings.docling_xbrl_enable_remote_fetch is False
    assert settings.docling_vlm_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.docling_pdf_picture_description_model == settings.docling_vlm_model
    assert settings.docling_engine_cache_enabled is True
    assert settings.docling_engine_warmup_enabled is False
    assert settings.parser_process_count == 2
    assert settings.parser_threads_per_process == 1
    assert settings.effective_docling_parse_concurrency == (
        settings.parser_threads_per_process
    )
    assert settings.docling_perf_page_batch_size == 32
    assert settings.docling_remote_llm_concurrency == 2
    assert settings.docling_pdf_picture_description_max_new_tokens == 2048
    assert settings.docling_remote_llm_page_batch_size is None


def test_cpu_env_loads() -> None:
    settings = Settings(_env_file="env-cpu")

    assert settings.docling_accelerator_device == "cpu"
    assert settings.docling_pdf_ocr_engine == "auto"
    assert settings.docling_pdf_ocr_use_gpu is False
    assert settings.docling_pdf_do_picture_classification is True
    assert settings.docling_pdf_do_picture_description is True
    assert settings.docling_pdf_picture_description_max_new_tokens == 2048
    assert settings.docling_engine_cache_enabled is True
    assert settings.docling_perf_page_batch_size == 32
    assert settings.docling_pdf_ocr_batch_size == 32
    assert settings.docling_pdf_queue_max_size == 512
    assert settings.chunking_strategy == "page"
    assert (
        str(settings.chunk_tokenizer_path)
        == "/datastore/models/tokenizers/qwen3-embedding-8b"
    )


def test_settings_use_requested_docling_standard_pipeline_defaults() -> None:
    settings = Settings()

    assert settings.parser_process_count == 2
    assert settings.parser_threads_per_process == 1
    assert settings.effective_docling_parse_concurrency == (
        settings.parser_threads_per_process
    )
    assert settings.docling_allow_external_plugins is True
    assert settings.docling_pdf_layout_model == "docling-layout-heron-101"
    assert settings.docling_pdf_ocr_engine == "suryaocr"
    assert settings.docling_pdf_ocr_languages == ["en"]
    assert settings.docling_pdf_table_structure_backend == "tableformer"
    assert settings.docling_pdf_table_structure_mode == "accurate"
    assert settings.docling_pdf_table_do_cell_matching is True
    assert settings.docling_pdf_do_picture_classification is True
    assert settings.docling_pdf_picture_classifier_preset == "document_figure_classifier_v2"
    assert settings.docling_pdf_do_picture_description is True
    assert settings.docling_pdf_picture_description_model == settings.docling_vlm_model
    assert settings.docling_pdf_picture_description_max_new_tokens == 2048
    assert settings.docling_remote_llm_concurrency == 2
    assert settings.docling_remote_llm_page_batch_size is None


def test_settings_parse_parser_process_and_thread_env_vars(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "INGEST_PARSER_PROCESS_COUNT=6",
                "INGEST_PARSER_THREADS_PER_PROCESS=2",
                "INGEST_DISPATCH_WORKER_COUNT=4",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.parser_process_count == 6
    assert settings.parser_threads_per_process == 2
    assert settings.parser_worker_count == 6
    assert settings.effective_docling_parse_concurrency == 2
    assert settings.dispatch_worker_count == 4


def test_settings_legacy_parser_worker_count_is_deprecated_process_alias() -> None:
    settings = Settings(parser_worker_count=5)

    assert settings.parser_process_count == 5
    assert settings.parser_worker_count == 5


def test_settings_new_parser_process_count_wins_over_legacy_alias() -> None:
    settings = Settings(parser_process_count=4, parser_worker_count=7)

    assert settings.parser_process_count == 4
    assert settings.parser_worker_count == 4


@pytest.mark.parametrize(
    "kwargs",
    [
        {"parser_process_count": 0},
        {"parser_process_count": -1},
        {"parser_threads_per_process": 0},
        {"parser_threads_per_process": -1},
        {"dispatch_worker_count": 0},
    ],
)
def test_settings_reject_non_positive_process_and_thread_counts(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(**kwargs)


def test_settings_normalize_legacy_chunking_strategy_alias() -> None:
    settings = Settings(chunking_strategy="hybrid")

    assert settings.chunking_strategy == "token"


def test_settings_do_not_expose_docling_ocr_defaults_as_fields() -> None:
    settings = Settings(
        docling_pdf_do_ocr=False,
        docling_pdf_ocr_languages="es",
    )

    assert "docling_pdf_do_ocr" not in Settings.model_fields
    assert "docling_pdf_ocr_languages" not in Settings.model_fields
    assert settings.docling_pdf_do_ocr is True
    assert settings.docling_pdf_ocr_languages == ["en"]


def test_settings_can_create_request_scoped_docling_ocr_languages() -> None:
    settings = Settings()
    requested_settings = settings.with_docling_pdf_ocr_languages(["es"])

    assert settings.docling_pdf_ocr_languages == ["en"]
    assert requested_settings.docling_pdf_ocr_languages == ["es"]
    assert requested_settings.docling_pdf_do_ocr is True


def test_docling_model_selection_settings_remain_env_configurable() -> None:
    settings = Settings(
        docling_pdf_layout_model="docling-layout-v2",
        docling_pdf_table_structure_backend="tableformer",
        docling_pdf_picture_classifier_preset="document_figure_classifier_v2",
    )

    assert settings.docling_pdf_layout_model == "docling-layout-v2"
    assert settings.docling_pdf_table_structure_backend == "tableformer"
    assert settings.docling_pdf_picture_classifier_preset == "document_figure_classifier_v2"


def test_docling_allowed_formats_are_derived_from_backend_upload_extensions() -> None:
    settings = Settings(allowed_upload_extensions=[".PDF", "md", ".png", ".jpg"])

    assert settings.docling_allowed_formats == ["image", "md", "pdf"]


def test_settings_do_not_expose_backend_vlm_loader_settings() -> None:
    removed_fields = {
        "docling_vlm_runtime",
        "docling_vlm_torch_dtype",
        "docling_vlm_load_in_8bit",
        "docling_vlm_max_new_tokens",
        "docling_vlm_trust_remote_code",
        "docling_pdf_picture_description_runtime",
        "docling_pdf_table_structure_vlm_model",
        "docling_pdf_do_code_enrichment",
        "docling_pdf_do_formula_enrichment",
        "docling_pdf_code_formula_preset",
        "docling_allowed_formats",
        "docling_parse_concurrency",
        "docling_gpu_engine_concurrency",
        "docling_gpu_batch_max_documents",
        "docling_gpu_batch_wait_ms",
        "docling_pdf_do_table_structure",
        "docling_pdf_table_structure_mode",
        "docling_pdf_table_do_cell_matching",
        "docling_pdf_do_picture_classification",
        "docling_pdf_do_picture_description",
        "docling_pdf_picture_description_model",
        "docling_pdf_picture_description_prompt",
        "docling_pdf_picture_description_max_new_tokens",
        "docling_pdf_do_ocr",
        "docling_pdf_ocr_languages",
    }

    assert removed_fields.isdisjoint(Settings.model_fields)


def test_settings_grouped_config_views() -> None:
    settings = Settings(
        docling_pipeline="vlm",
        parser_process_count=3,
        parser_threads_per_process=2,
    )

    assert settings.docling_common_config.pipeline == "vlm"
    assert settings.docling_common_config.parse_concurrency == 2
    assert settings.docling_common_config.engine_cache_enabled is True
    assert settings.docling_vlm_config.remote_llm_url == (
        "http://localhost:8000/v1/chat/completions"
    )
    assert settings.docling_vlm_config.remote_llm_max_tokens == 4096
    assert settings.docling_xbrl_config.enable_local_fetch is False
    assert settings.chunking_config.embedding_output_enabled is True
    assert settings.confidence_config.output_enabled is True
    assert settings.dispatch_config.max_bulk_size == 5
    assert settings.dispatch_config.parser_process_count == 3
    assert settings.dispatch_config.parser_threads_per_process == 2
    assert settings.dispatch_config.parser_worker_count == 3
    assert settings.dispatch_config.dispatch_worker_count == 2
    assert settings.dispatch_config.queue_backend == "local"
    assert settings.dispatch_config.rabbitmq_configured is True
    assert settings.dispatch_config.queue_max_payload_bytes is None
    assert settings.dispatch_config.dramatiq_parser_time_limit_ms == 14_400_000
    assert settings.dispatch_config.dramatiq_dispatch_time_limit_ms == 600_000
    assert settings.dispatch_config.parser_max_retries == 3
    assert settings.dispatch_config.sink_mode == "local"
    assert settings.dispatch_config.elastic_mapping_version == "v1"
    assert settings.dispatch_config.elastic_password_configured is False


def test_settings_normalize_elastic_mapping_version_aliases() -> None:
    semantic_settings = Settings(embedding_elastic_mapping_version="semantic-text-v2")
    dense_vector_settings = Settings(embedding_elastic_mapping_version="dense_vector_v1")

    assert semantic_settings.embedding_elastic_mapping_version == "v2"
    assert dense_vector_settings.embedding_elastic_mapping_version == "v1"


def test_settings_reject_unknown_elastic_mapping_version() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_elastic_mapping_version="v3")


def test_settings_reject_unknown_queue_backend() -> None:
    with pytest.raises(ValidationError):
        Settings(queue_backend="sqs")


def test_settings_reject_dispatch_bulk_size_over_five() -> None:
    with pytest.raises(ValidationError):
        Settings(dispatch_max_bulk_size=6)


def test_settings_dispatch_config_redacts_password() -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_username="user",
        embedding_elastic_password="secret",
    )

    config = settings.dispatch_config.model_dump()

    assert config["elastic_password_configured"] is True
    assert "secret" not in str(config)
