from pathlib import Path


class FakeDoclingConverter:
    def convert(self, source_path: Path) -> object:
        return FakeDoclingConversionResult(source_path)


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
            "texts": [],
        }

    def export_to_markdown(self) -> str:
        return "# Example"

    def export_to_text(self) -> str:
        return "Example"

    def export_to_html(self) -> str:
        return "<h1>Example</h1>"
