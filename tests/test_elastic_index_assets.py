import json
from pathlib import Path


def test_open_rag_embedding_index_asset_maps_chunk_documents() -> None:
    asset_path = Path("elastic/open-rag-embeddings-v1.json")

    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    properties = asset["index"]["mappings"]["properties"]
    inference = asset["pipeline"]["processors"][1]["inference"]

    assert asset["index_name"] == "open-rag-embeddings-v1"
    assert asset["index"]["mappings"]["_source"]["excludes"] == [
        "content_embedding",
        "title_embedding",
    ]
    assert properties["content_embedding"]["dims"] == 4096
    assert properties["content_embedding"]["index_options"]["type"] == "int8_hnsw"
    assert properties["title_embedding"]["dims"] == 4096
    assert properties["title_embedding"]["index_options"]["type"] == "int8_hnsw"
    assert properties["record_id"]["type"] == "keyword"
    assert properties["document_id"]["type"] == "keyword"
    assert properties["job_id"]["type"] == "keyword"
    assert properties["chunk_id"]["type"] == "keyword"
    assert properties["record_type"]["type"] == "keyword"
    assert properties["confidence"]["properties"]["mean_score"]["type"] == "float"
    for field_name in [
        "raw_text",
        "schema_version",
        "metadata",
        "runtime",
        "element_ids",
        "profile",
        "vlm_model",
        "vlm_runtime",
        "picture_description_model",
        "picture_description_runtime",
    ]:
        assert field_name not in properties
    assert inference["model_id"] == "qwen3-embedding-8b"
    assert inference["input_output"] == [
        {
            "input_field": "content",
            "output_field": "content_embedding",
        },
        {
            "input_field": "title",
            "output_field": "title_embedding",
        },
    ]


def test_open_rag_embedding_v2_index_asset_uses_semantic_text_without_auto_chunking() -> None:
    asset_path = Path("elastic/open-rag-embeddings-v2.json")

    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    mappings = asset["index"]["mappings"]
    settings = asset["index"]["settings"]
    properties = mappings["properties"]
    processors = asset["pipeline"]["processors"]

    assert asset["index_name"] == "open-rag-embeddings-v2"
    assert asset["pipeline_name"] == "open_rag_embeddings_v2_semantic_pipeline"
    assert settings["index.default_pipeline"] == "open_rag_embeddings_v2_semantic_pipeline"
    assert "_source" not in mappings
    assert mappings["_meta"]["inference_id"] == "qwen3-embedding-8b"
    assert "content_embedding" not in properties
    assert "title_embedding" not in properties
    assert properties["content"]["type"] == "text"
    assert properties["title"]["type"] == "text"
    assert properties["title"]["fields"]["keyword"]["type"] == "keyword"

    for field_name in ["content_semantic", "title_semantic"]:
        field = properties[field_name]
        assert field["type"] == "semantic_text"
        assert field["inference_id"] == "qwen3-embedding-8b"
        assert field["index_options"]["dense_vector"] == {
            "element_type": "float",
            "type": "int8_hnsw",
        }
        assert field["chunking_settings"] == {"strategy": "none"}

    assert properties["record_id"]["type"] == "keyword"
    assert properties["document_id"]["type"] == "keyword"
    assert properties["job_id"]["type"] == "keyword"
    assert properties["chunk_id"]["type"] == "keyword"
    assert properties["record_type"]["type"] == "keyword"
    for field_name in [
        "raw_text",
        "schema_version",
        "metadata",
        "runtime",
        "element_ids",
        "profile",
        "vlm_model",
        "vlm_runtime",
        "picture_description_model",
        "picture_description_runtime",
    ]:
        assert field_name not in properties
    assert processors == [
        {
            "set": {
                "field": "ingested_at",
                "value": "{{{_ingest.timestamp}}}",
            }
        },
        {
            "script": {
                "lang": "painless",
                "source": (
                    "if (ctx.content != null) { ctx.content_semantic = "
                    "ctx.content.replace('${', '$ {'); } "
                    "if (ctx.title != null) { ctx.title_semantic = "
                    "ctx.title.replace('${', '$ {'); }"
                ),
            }
        },
    ]
