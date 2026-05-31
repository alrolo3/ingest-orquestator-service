from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def _ctx():
    from ingest_orquestator_server.infrastructure.docling.docling_progress import (
        current_docling_progress_context,
    )

    return current_docling_progress_context()


def _model_names(models: list[Any]) -> list[str]:
    from ingest_orquestator_server.infrastructure.docling.docling_progress import (
        progress_model_names,
    )

    return progress_model_names(models)


class ProgressStandardPdfPipeline:
    """Mixin injected ahead of Docling's StandardPdfPipeline."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.pipeline.initializing",
                message="Loading Docling standard PDF pipeline models.",
                details={"pipeline_class": type(self).__name__},
            )
        super().__init__(*args, **kwargs)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.pipeline.initialized",
                message="Docling standard PDF pipeline models are loaded.",
                details={
                    "build_models": [
                        "PagePreprocessingModel",
                        type(self.ocr_model).__name__,
                        type(self.layout_model).__name__,
                        type(self.table_model).__name__,
                        type(self.assemble_model).__name__,
                    ],
                    "enrichment_models": _model_names(self.enrichment_pipe),
                },
            )

    def _build_document(self, conv_res: Any) -> Any:
        ctx = _ctx()
        if ctx is not None:
            page_count = len(self._get_expected_page_nos(conv_res))
            ctx.report(
                stage="docling.document_build.started",
                message="Docling standard PDF page pipeline started.",
                page_count=page_count,
                pages_completed=0,
            )
        result = super()._build_document(conv_res)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.document_build.completed",
                message="Docling standard PDF page pipeline completed.",
                pages_completed=ctx.pages_completed,
            )
        return result

    def _create_run_ctx(self) -> Any:
        run_ctx = super()._create_run_ctx()
        ctx = _ctx()
        if ctx is None:
            return run_ctx

        for stage in run_ctx.stages:
            if stage.name != "assemble":
                continue
            original_postprocess = stage._postprocess

            def _postprocess(
                item: Any,
                postprocess: Callable[[Any], None] | None = original_postprocess,
            ) -> None:
                if postprocess is not None:
                    postprocess(item)
                ctx.mark_page_completed(
                    int(item.page_no),
                    stage="docling.standard_pdf.page.completed",
                    component="docling.standard_pdf",
                )

            stage._postprocess = _postprocess
        return run_ctx

    def _assemble_document(self, conv_res: Any) -> Any:
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.document_assemble.started",
                message="Assembling Docling document structure.",
            )
        result = super()._assemble_document(conv_res)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.document_assemble.completed",
                message="Docling document structure assembled.",
            )
        return result

    def _enrich_document(self, conv_res: Any) -> Any:
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.enrichment.started",
                message="Running Docling enrichment models.",
                details={"models": _model_names(self.enrichment_pipe)},
            )
        result = super()._enrich_document(conv_res)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.enrichment.completed",
                message="Docling enrichment models completed.",
            )
        return result


class ProgressVlmPipeline:
    """Mixin injected ahead of Docling's VlmPipeline."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.vlm_pipeline.initializing",
                message="Loading Docling VLM pipeline model.",
                details={"pipeline_class": type(self).__name__},
            )
        super().__init__(*args, **kwargs)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.vlm_pipeline.initialized",
                message="Docling VLM pipeline model is loaded.",
                details={"build_models": _model_names(self.build_pipe)},
            )

    def _build_document(self, conv_res: Any) -> Any:
        ctx = _ctx()
        if ctx is not None:
            start_page, end_page = conv_res.input.limits.page_range
            page_count = max(
                0,
                min(conv_res.input.page_count, end_page) - max(1, start_page) + 1,
            )
            ctx.report(
                stage="docling.vlm_document_build.started",
                message="Docling VLM page conversion started.",
                page_count=page_count,
                pages_completed=0,
            )
        result = super()._build_document(conv_res)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.vlm_document_build.completed",
                message="Docling VLM page conversion completed.",
                pages_completed=ctx.pages_completed,
            )
        return result

    def _apply_on_pages(self, conv_res: Any, page_batch: Iterable[Any]) -> Iterable[Any]:
        ctx = _ctx()
        for page in super()._apply_on_pages(conv_res, page_batch):
            if ctx is not None:
                ctx.mark_page_completed(
                    int(page.page_no),
                    stage="docling.vlm.page.completed",
                    component="docling.vlm",
                )
            yield page

    def _assemble_document(self, conv_res: Any) -> Any:
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.vlm_document_assemble.started",
                message="Assembling VLM page output into a Docling document.",
            )
        result = super()._assemble_document(conv_res)
        ctx = _ctx()
        if ctx is not None:
            ctx.report(
                stage="docling.vlm_document_assemble.completed",
                message="VLM document assembly completed.",
            )
        return result
