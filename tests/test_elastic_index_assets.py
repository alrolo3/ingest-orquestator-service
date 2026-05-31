import json
from pathlib import Path


def test_open_rag_embedding_index_asset_maps_chunk_documents() -> None:
    asset_path = Path("elastic/open-rag-embeddings-v1.json")

    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    properties = asset["index"]["mappings"]["properties"]
    inference = asset["pipeline"]["processors"][1]["inference"]

    assert asset["index_name"] == "open-rag-embeddings-v1"
    assert properties["content_embedding"]["dims"] == 4096
    assert properties["content_embedding"]["index_options"]["type"] == "int8_hnsw"
    assert properties["title_embedding"]["dims"] == 4096
    assert properties["title_embedding"]["index_options"]["type"] == "int8_hnsw"
    assert properties["record_id"]["type"] == "keyword"
    assert properties["document_id"]["type"] == "keyword"
    assert properties["chunk_id"]["type"] == "keyword"
    assert properties["metadata"]["enabled"] is False
    assert properties["confidence"]["properties"]["mean_score"]["type"] == "float"
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
