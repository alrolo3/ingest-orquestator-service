from pathlib import Path

from ingest_orquestator_server.models import ParsedDocument, ParseOutput
from ingest_orquestator_server.output_writer import write_parse_output


def test_write_parse_output_writes_expected_artifacts(tmp_path: Path) -> None:
    parse_output = ParseOutput(
        document=ParsedDocument(
            document_id="doc-1",
            source_file_name="example.pdf",
            source_path="/tmp/example.pdf",
            markdown="# Hello",
            text="Hello",
        ),
        raw_docling={"name": "example"},
        raw_markdown="# Hello",
        raw_text="Hello",
        raw_html="<h1>Hello</h1>",
    )

    outputs = write_parse_output(parse_output, tmp_path)

    assert outputs.output_dir.exists()
    assert outputs.raw_docling_json.read_text(encoding="utf-8")
    assert outputs.normalized_json.read_text(encoding="utf-8")
    assert outputs.markdown.read_text(encoding="utf-8") == "# Hello"
    assert outputs.text.read_text(encoding="utf-8") == "Hello"
    assert outputs.html is not None
    assert outputs.html.read_text(encoding="utf-8") == "<h1>Hello</h1>"
    assert outputs.manifest_json.exists()
