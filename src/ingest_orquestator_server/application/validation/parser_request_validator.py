from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ingest_orquestator_server.config.settings import Settings


class ParserSpecificRequestValidator(Protocol):
    def validate(
        self,
        *,
        filename: str,
        pipeline: str | None,
        chunking_strategy: str | None = None,
    ) -> None: ...


class ParserRequestValidator(Protocol):
    def validate(
        self,
        *,
        filename: str,
        parser_name: str,
        pipeline: str | None,
        chunking_strategy: str | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class ParserRequestValidationService:
    validators: Mapping[str, ParserSpecificRequestValidator]

    def validate(
        self,
        *,
        filename: str,
        parser_name: str,
        pipeline: str | None,
        chunking_strategy: str | None = None,
    ) -> None:
        validator = self.validators.get(parser_name)
        if validator is None:
            return
        validator.validate(
            filename=filename,
            pipeline=pipeline,
            chunking_strategy=chunking_strategy,
        )


def build_default_parser_request_validator(settings: Settings) -> ParserRequestValidator:
    # Compatibility fallback for direct FileIngestionService construction.
    from ingest_orquestator_server.infrastructure.parser.parser_request_validator_factory import (
        build_parser_request_validator,
    )

    return build_parser_request_validator(settings)
