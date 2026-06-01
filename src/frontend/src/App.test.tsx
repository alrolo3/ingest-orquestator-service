import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/queue/metrics")) {
          return new Response(
            JSON.stringify({
              queue_backend: "local",
              parser_queue_name: "ingest-parser",
              dispatch_queue_name: "ingest-dispatch",
              parser_worker_count: 2,
              dispatch_worker_count: 3,
              status_counts: { parser_queued: 1, completed: 4 },
              stages: [
                {
                  name: "parser_queue",
                  statuses: ["parser_queued"],
                  count: 1,
                  jobs: [
                    {
                      job_id: "job-1",
                      status: "parser_queued",
                      parser: "docling",
                      source_file_name: "example.pdf",
                      metadata: {},
                      created_at: "2026-01-01T00:00:00Z",
                      updated_at: "2026-01-01T00:00:00Z",
                    },
                  ],
                },
                { name: "dispatch_queue", statuses: ["dispatch_queued"], count: 0, jobs: [] },
                { name: "failed", statuses: ["failed"], count: 0, jobs: [] },
              ],
              dispatch_queue: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({
            service: "ingest-orquestator-server",
            max_upload_size_mb: 100,
            allowed_upload_extensions: [".pdf", ".md"],
            parsers: [{ value: "docling", label: "Docling", default: true }],
            pipelines: [
              { value: "standard", label: "Standard", default: true },
              { value: "vlm", label: "VLM" },
              { value: "auto", label: "Auto" },
            ],
            default_parser: "docling",
            default_pipeline: "standard",
            default_dispatch_sink_mode: "local",
            dispatchers: [
              { value: "local", label: "Local", default: true },
              { value: "elastic", label: "Elastic" },
              { value: "local_and_elastic", label: "Local And Elastic" },
            ],
            ocr: {
              enabled: true,
              engine: "suryaocr",
              default_languages: ["en"],
              languages: [
                { value: "en", label: "English", default: true },
                { value: "es", label: "Spanish" },
              ],
            },
            chunking: {
              enabled: true,
              default_strategy: "hybrid",
              strategies: [
                { value: "hybrid", label: "Hybrid" },
                { value: "line_based", label: "Line Based" },
              ],
            },
            runtime: {},
            output_types: ["metadata", "markdown", "rag", "html"],
            job_statuses: ["parser_queued", "parsing", "completed", "failed"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the ingestion workspace as the first screen", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Ingest Orquestator" })).toBeInTheDocument();
    expect(screen.getByText("Drop files or browse")).toBeInTheDocument();
    expect(await screen.findByText(".pdf, .md up to 100 MB")).toBeInTheDocument();
  });

  it("renders dispatcher, OCR, and queue metric controls", async () => {
    render(<App />);

    expect(await screen.findByLabelText("Dispatcher")).toBeInTheDocument();
    expect(screen.getByLabelText("OCR language")).toBeInTheDocument();
    expect(screen.getByLabelText("HTML output")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Queue metrics" }));

    expect(await screen.findByText("ingest-parser")).toBeInTheDocument();
    expect(screen.getByText("example.pdf")).toBeInTheDocument();
  });
});
