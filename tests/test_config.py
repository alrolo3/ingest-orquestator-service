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
        assert expected <= actual


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
    assert settings.chunking_enabled is True
    assert settings.chunking_strategy == "hybrid"
    assert settings.confidence_output_enabled is True
    assert settings.docling_accelerator_device == "cuda"
    assert settings.docling_xbrl_enable_local_fetch is True
    assert settings.docling_pdf_picture_description_runtime == "transformers"
    assert settings.docling_vlm_runtime == "transformers"
    assert settings.docling_remote_llm_url == "http://localhost:8000/v1/chat/completions"
    assert settings.docling_remote_llm_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.docling_remote_llm_concurrency == 8
    assert settings.docling_vlm_max_new_tokens == 4096
    assert settings.docling_pdf_picture_description_max_new_tokens == 1024
    assert settings.effective_docling_vlm_trust_remote_code is False
    assert settings.docling_remote_llm_page_batch_size == 8
    assert settings.parser_worker_count == 2
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
    assert settings.docling_vlm_runtime == "transformers"
    assert settings.docling_pdf_picture_description_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.docling_pdf_picture_description_runtime == "transformers"
    assert settings.docling_remote_llm_concurrency == 8
    assert settings.docling_vlm_max_new_tokens == 4096
    assert settings.docling_pdf_picture_description_max_new_tokens == 1024
    assert settings.docling_remote_llm_page_batch_size == 8
    assert settings.effective_docling_vlm_trust_remote_code is False


def test_cpu_env_loads() -> None:
    settings = Settings(_env_file="env-cpu")

    assert settings.docling_accelerator_device == "cpu"
    assert settings.docling_pdf_ocr_engine == "auto"
    assert settings.docling_pdf_ocr_use_gpu is False
    assert settings.docling_pdf_do_picture_classification is False
    assert settings.docling_pdf_do_picture_description is False
    assert settings.docling_pdf_picture_description_max_new_tokens == 1024
    assert settings.docling_pdf_do_code_enrichment is False
    assert settings.docling_pdf_do_formula_enrichment is False
    assert settings.docling_pdf_picture_description_runtime == "transformers"
    assert settings.docling_pdf_ocr_batch_size == 1
    assert settings.docling_pdf_queue_max_size == 32
    assert settings.chunking_strategy == "hybrid"


def test_settings_use_requested_docling_standard_pipeline_defaults() -> None:
    settings = Settings()

    assert settings.docling_allow_external_plugins is True
    assert settings.docling_pdf_layout_model == "docling-layout-heron-101"
    assert settings.docling_pdf_ocr_engine == "suryaocr"
    assert settings.docling_pdf_ocr_languages == ["en"]
    assert settings.docling_pdf_table_structure_backend == "tableformer"
    assert settings.docling_pdf_table_structure_mode == "accurate"
    assert settings.docling_pdf_table_do_cell_matching is True
    assert settings.docling_pdf_table_structure_vlm_model == "granite-vision-4.1-4b"
    assert settings.docling_pdf_do_picture_classification is True
    assert settings.docling_pdf_picture_classifier_preset == "document_figure_classifier_v2"
    assert settings.docling_pdf_do_picture_description is True
    assert settings.docling_pdf_picture_description_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.docling_pdf_picture_description_runtime == "transformers"
    assert settings.docling_pdf_picture_description_max_new_tokens == 1024
    assert settings.docling_pdf_do_code_enrichment is True
    assert settings.docling_pdf_do_formula_enrichment is True
    assert settings.docling_pdf_code_formula_preset == "codeformulav2"


def test_settings_parse_docling_ocr_languages_from_string() -> None:
    settings = Settings(docling_pdf_ocr_languages="en,es")

    assert settings.docling_pdf_ocr_languages == ["en", "es"]


def test_settings_parse_docling_allowed_formats_from_string() -> None:
    settings = Settings(docling_allowed_formats="pdf, image, docx")

    assert settings.docling_allowed_formats == ["docx", "image", "pdf"]


def test_settings_reject_unknown_docling_format() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_allowed_formats=["pdf", "unknown"])


def test_settings_grouped_config_views() -> None:
    settings = Settings(docling_pipeline="vlm", docling_vlm_runtime="transformers")

    assert settings.docling_common_config.pipeline == "vlm"
    assert settings.docling_vlm_config.runtime == "transformers"
    assert settings.docling_vlm_config.remote_llm_url == (
        "http://localhost:8000/v1/chat/completions"
    )
    assert settings.docling_vlm_config.max_new_tokens == 4096
    assert settings.docling_xbrl_config.enable_local_fetch is False
    assert settings.chunking_config.embedding_output_enabled is True
    assert settings.confidence_config.output_enabled is True
    assert settings.dispatch_config.max_bulk_size == 5
    assert settings.dispatch_config.queue_max_payload_bytes is None
    assert settings.dispatch_config.sink_mode == "local"
    assert settings.dispatch_config.elastic_mapping_version == "v1"
    assert settings.dispatch_config.elastic_password_configured is False
    assert settings.dispatch_config.elastic_include_local_paths is False


def test_settings_normalize_elastic_mapping_version_aliases() -> None:
    semantic_settings = Settings(embedding_elastic_mapping_version="semantic-text-v2")
    dense_vector_settings = Settings(embedding_elastic_mapping_version="dense_vector_v1")

    assert semantic_settings.embedding_elastic_mapping_version == "v2"
    assert dense_vector_settings.embedding_elastic_mapping_version == "v1"


def test_settings_reject_unknown_elastic_mapping_version() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_elastic_mapping_version="v3")


def test_settings_reject_dispatch_bulk_size_over_five() -> None:
    with pytest.raises(ValidationError):
        Settings(dispatch_max_bulk_size=6)


def test_settings_embedding_queue_config_redacts_password() -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_username="user",
        embedding_elastic_password="secret",
    )

    config = settings.dispatch_config.model_dump()

    assert config["elastic_password_configured"] is True
    assert "secret" not in str(config)


def test_settings_vlm_trust_remote_code_overrides_legacy_vllm_alias() -> None:
    settings = Settings(
        docling_vlm_trust_remote_code=True,
        docling_vllm_trust_remote_code=False,
    )

    assert settings.effective_docling_vlm_trust_remote_code is True
    assert settings.docling_vlm_config.trust_remote_code is True


def test_settings_legacy_vllm_trust_remote_code_still_works() -> None:
    settings = Settings(docling_vllm_trust_remote_code=True)

    assert settings.effective_docling_vlm_trust_remote_code is True


def test_settings_reject_unknown_table_structure_backend() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_pdf_table_structure_backend="unknown")


def test_settings_reject_unknown_vlm_runtime() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_vlm_runtime="unknown")


def test_settings_maps_legacy_vllm_runtime_to_remote_llm() -> None:
    settings = Settings(
        docling_vlm_runtime="vllm",
        docling_pdf_picture_description_runtime="vllm",
    )

    assert settings.docling_vlm_runtime == "remote_llm"
    assert settings.docling_pdf_picture_description_runtime == "remote_llm"


def test_settings_reject_unknown_picture_description_runtime() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_pdf_picture_description_runtime="unknown")
