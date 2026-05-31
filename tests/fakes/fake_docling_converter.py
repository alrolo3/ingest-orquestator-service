from pathlib import Path


class FakeDoclingConverter:
    def __init__(self) -> None:
        self.initialize_count = 0
        self.convert_count = 0
        self.convert_all_count = 0
        self.initialized_formats: list[str] = []

    def initialize_pipeline(self, input_format: object) -> None:
        self.initialize_count += 1
        self.initialized_formats.append(getattr(input_format, "value", str(input_format)))

    def convert(self, source_path: Path) -> object:
        self.convert_count += 1
        return FakeDoclingConversionResult(source_path)

    def convert_all(
        self,
        source_paths: list[Path],
        *,
        raises_on_error: bool = True,
    ) -> object:
        _ = raises_on_error
        self.convert_all_count += 1
        self.convert_count += len(source_paths)
        return (FakeDoclingConversionResult(source_path) for source_path in source_paths)


class FakeDoclingConversionResult:
    def __init__(self, source_path: Path) -> None:
        self.document = FakeDoclingDocument(source_path)


class FakeDoclingDocument:
    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def export_to_dict(self) -> dict[str, object]:
        return {
            "name": self.source_path.stem,
            "origin": {"filename": self.source_path.name},
            "pages": {},
            "texts": [
                {
                    "self_ref": "#/texts/0",
                    "label": "paragraph",
                    "text": "Example",
                    "prov": [{"page_no": 1}],
                }
            ],
        }

    def export_to_markdown(self) -> str:
        return "# Example"

    def export_to_text(self) -> str:
        return "Example"

    def export_to_html(self) -> str:
        return "<h1>Example</h1>"
