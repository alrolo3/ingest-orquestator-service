class UnsupportedParserError(ValueError):
    def __init__(self, parser_name: str) -> None:
        super().__init__(f"Unsupported parser: {parser_name}")
        self.parser_name = parser_name


class UploadValidationError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class JobNotFoundError(LookupError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Ingestion job not found: {job_id}")
        self.job_id = job_id


class OutputArtifactNotFoundError(LookupError):
    def __init__(self, job_id: str, output_type: str) -> None:
        super().__init__(f"Output artifact not found for job {job_id}: {output_type}")
        self.job_id = job_id
        self.output_type = output_type
