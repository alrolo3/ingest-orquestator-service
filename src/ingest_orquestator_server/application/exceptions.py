class UnsupportedParserError(ValueError):
    def __init__(self, parser_name: str) -> None:
        super().__init__(f"Unsupported parser: {parser_name}")
        self.parser_name = parser_name
