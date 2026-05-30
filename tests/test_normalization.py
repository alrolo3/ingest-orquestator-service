from pathlib import Path

from ingest_orquestator_server.normalizers.docling.docling_document_normalizer import (
    DoclingDocumentNormalizer,
)


def test_normalize_docling_document_extracts_pages_and_elements() -> None:
    raw_docling = {
        "schema_name": "DoclingDocument",
        "version": "1.0.0",
        "name": "Example",
        "origin": {"filename": "example.pdf", "mimetype": "application/pdf"},
        "pages": {"1": {"size": {"width": 100, "height": 200}}},
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "section_header",
                "text": "Overview",
                "prov": [{"page_no": 1, "bbox": {"l": 1, "t": 2, "r": 3, "b": 4}}],
            }
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "label": "table",
                "prov": [{"page_no": 1}],
                "data": {
                    "table_cells": [
                        {
                            "text": "Name",
                            "start_row_offset_idx": 0,
                            "end_row_offset_idx": 1,
                            "start_col_offset_idx": 0,
                            "end_col_offset_idx": 1,
                        },
                        {
                            "text": "Value",
                            "start_row_offset_idx": 0,
                            "end_row_offset_idx": 1,
                            "start_col_offset_idx": 1,
                            "end_col_offset_idx": 2,
                        },
                    ]
                },
            }
        ],
    }

    parsed = DoclingDocumentNormalizer().normalize(
        raw_docling=raw_docling,
        source_path=Path("/tmp/example.pdf"),
        document_id="doc-1",
        markdown="# Overview",
        text="Overview",
        mime_type="application/pdf",
    )

    assert parsed.document_id == "doc-1"
    assert parsed.source_file_name == "example.pdf"
    assert parsed.page_count == 1
    assert parsed.pages[0].width == 100
    assert [element.type for element in parsed.elements] == ["heading", "table"]
    assert parsed.elements[1].markdown is not None
