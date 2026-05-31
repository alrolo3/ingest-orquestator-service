from pathlib import Path

import pytest

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
    UnsupportedIngestionOptionError,
    UnsupportedPipelineError,
)
from ingest_orquestator_server.application.validation.parser_request_validator import (
    ParserRequestValidationService,
)
from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_parser_request_validator import (
    DoclingParserRequestValidator,
)


def test_parser_request_validator_accepts_docling_standard_markdown(tmp_path: Path) -> None:
    validator = ParserRequestValidationService(
        {"docling": DoclingParserRequestValidator(Settings(storage_dir=tmp_path))}
    )

    validator.validate(
        filename="example.md",
        parser_name="docling",
        pipeline="standard",
    )


def test_parser_request_validator_rejects_docling_vlm_for_markdown(tmp_path: Path) -> None:
    validator = ParserRequestValidationService(
        {"docling": DoclingParserRequestValidator(Settings(storage_dir=tmp_path))}
    )

    with pytest.raises(UnsupportedPipelineError, match="PDF and image"):
        validator.validate(
            filename="example.md",
            parser_name="docling",
            pipeline="vlm",
        )


def test_parser_request_validator_ignores_unknown_parser(tmp_path: Path) -> None:
    validator = ParserRequestValidationService(
        {"docling": DoclingParserRequestValidator(Settings(storage_dir=tmp_path))}
    )

    validator.validate(
        filename="example.unknown",
        parser_name="custom",
        pipeline="vlm",
        chunking_strategy="unknown",
    )


def test_parser_request_validator_rejects_disabled_docling_format(tmp_path: Path) -> None:
    validator = ParserRequestValidationService(
        {
            "docling": DoclingParserRequestValidator(
                Settings(storage_dir=tmp_path, docling_allowed_formats=["pdf"])
            )
        }
    )

    with pytest.raises(UnsupportedDocumentFormatError, match="disabled"):
        validator.validate(
            filename="example.md",
            parser_name="docling",
            pipeline="standard",
        )


def test_parser_request_validator_rejects_docling_chunking_strategy(tmp_path: Path) -> None:
    validator = ParserRequestValidationService(
        {"docling": DoclingParserRequestValidator(Settings(storage_dir=tmp_path))}
    )

    with pytest.raises(UnsupportedIngestionOptionError, match="chunking_strategy"):
        validator.validate(
            filename="example.md",
            parser_name="docling",
            pipeline="standard",
            chunking_strategy="unknown",
        )
