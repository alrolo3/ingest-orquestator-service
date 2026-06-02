import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
              parser_process_count: 2,
              parser_threads_per_process: 1,
              active_parser_job_count: 1,
              queued_parser_job_count: 1,
              stale_parser_job_count: 0,
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
                { name: "active_parser_jobs", statuses: ["parsing"], count: 1, jobs: [] },
                { name: "dispatch_queue", statuses: ["dispatch_queued"], count: 0, jobs: [] },
                { name: "failed", statuses: ["failed"], count: 0, jobs: [] },
              ],
              dispatch_queue: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (String(input).includes("/settings")) {
          return new Response(
            JSON.stringify({
              fields: [
                {
                  key: "docling_accelerator_device",
                  env_var: "INGEST_DOCLING_ACCELERATOR_DEVICE",
                  label: "Docling Accelerator Device",
                  group: "Docling runtime",
                  kind: "text",
                  value: "cpu",
                  source: "env",
                  configured: true,
                  secret: false,
                  options: [],
                },
                {
                  key: "embedding_elastic_password",
                  env_var: "INGEST_EMBEDDING_ELASTIC_PASSWORD",
                  label: "Embedding Elastic Password",
                  group: "Dispatch",
                  kind: "secret",
                  value: null,
                  source: "env",
                  configured: true,
                  secret: true,
                  options: [],
                },
                {
                  key: "max_upload_size_mb",
                  env_var: "INGEST_MAX_UPLOAD_SIZE_MB",
                  label: "Max Upload Size MB",
                  group: "Upload",
                  kind: "integer",
                  value: 100,
                  source: "env",
                  configured: true,
                  secret: false,
                  options: [],
                },
              ],
              boot_time_keys: ["storage_dir"],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({
            service: "ingest-orquestator-server",
            max_upload_size_mb: 100,
            allowed_upload_extensions: [".pdf", ".md"],
            parsers: [
              {
                value: "docling",
                label: "Docling",
                default: true,
                chunking: {
                  enabled: true,
                  default_strategy: "page",
                  strategies: [
                    { value: "token", label: "Token" },
                    { value: "page", label: "Page" },
                  ],
                },
              },
            ],
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
              default_strategy: "page",
              strategies: [
                { value: "token", label: "Token" },
                { value: "page", label: "Page" },
                { value: "line", label: "Line" },
              ],
              by_parser: {
                docling: {
                  enabled: true,
                  default_strategy: "page",
                  strategies: [
                    { value: "token", label: "Token" },
                    { value: "page", label: "Page" },
                  ],
                },
              },
            },
            runtime: {},
            output_types: ["metadata", "markdown", "rag", "html"],
            job_statuses: ["parser_queued", "retrying", "parsing", "completed", "failed"],
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
    expect(screen.getByText("Parser processes")).toBeInTheDocument();
    expect(screen.getByText("Active parser jobs")).toBeInTheDocument();
    expect(screen.getByText("example.pdf")).toBeInTheDocument();
  });

  it("renders and saves the ingestor settings panel", async () => {
    const fetch = vi.mocked(globalThis.fetch);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Ingestor settings" }));

    expect(
      await screen.findByRole("navigation", { name: "Ingestor settings sections" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Docling runtime settings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    fireEvent.click(screen.getByRole("button", { name: "Dispatch settings" }));
    expect(screen.getByPlaceholderText("Configured")).toHaveAttribute(
      "placeholder",
      "Configured",
    );
    fireEvent.click(screen.getByRole("button", { name: "Docling runtime settings" }));

    const accelerator = await screen.findByRole("textbox", {
      name: /Docling Accelerator Device/,
    });
    fireEvent.change(accelerator, { target: { value: "cuda" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/v1/ingest/settings",
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("docling_accelerator_device"),
        }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Dispatch settings" }));
    expect(screen.getByPlaceholderText("Configured")).toBeInTheDocument();
  });

  it("keeps invalid numeric setting drafts for backend validation", async () => {
    const fetch = vi.mocked(globalThis.fetch);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Ingestor settings" }));

    fireEvent.click(await screen.findByRole("button", { name: "Upload settings" }));
    const maxUploadSize = await screen.findByRole("textbox", {
      name: /Max Upload Size MB/,
    });
    fireEvent.change(maxUploadSize, { target: { value: "12abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/v1/ingest/settings",
        expect.objectContaining({ method: "PATCH" }),
      ),
    );

    const patchCall = fetch.mock.calls.find(
      ([url, init]) => String(url).includes("/settings") && init?.method === "PATCH",
    );
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({
      values: { max_upload_size_mb: "12abc" },
    });
  });

  it("removes a tracked job from the ingestor service", async () => {
    const job = {
      job_id: "job-1",
      status: "parser_queued",
      parser: "docling",
      source_file_name: "example.pdf",
      metadata: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    localStorage.setItem(
      "ingest-orquestator.frontend.jobs",
      JSON.stringify([
        {
          local_id: "local-1",
          file_name: "example.pdf",
          file_size: 10,
          submitted_at: "2026-01-01T00:00:00Z",
          job_id: "job-1",
          response: job,
          job,
        },
      ]),
    );
    const fallbackFetch = globalThis.fetch;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/runs?ids=")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              runs: [
                {
                  ...job,
                  run_id: "job-1",
                  document_id: "doc-1",
                  attempt_number: 1,
                  status_url: "/v1/ingest/runs/job-1",
                  outputs_url: "/v1/ingest/runs/job-1/outputs",
                },
              ],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        );
      }
      if (url.includes("/jobs?ids=")) {
        return Promise.resolve(
          new Response(JSON.stringify([job]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.endsWith("/v1/ingest/jobs/job-1") && init?.method === "DELETE") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              job_id: "job-1",
              previous_status: "parser_queued",
              removed: true,
              parser_process_terminated: false,
              removed_dispatch_queue_item: false,
              removed_artifact_count: 0,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return fallbackFetch(input, init);
    }));

    render(<App />);

    expect(await screen.findByText("example.pdf")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove job example.pdf" }));

    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/v1/ingest/jobs/job-1",
        { method: "DELETE" },
      ),
    );
    expect(screen.queryByText("example.pdf")).not.toBeInTheDocument();
  });

  it("groups repeated uploads of the same document and shows run history", async () => {
    const fallbackFetch = globalThis.fetch;
    let uploadCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/documents") && init?.method === "POST") {
          uploadCount += 1;
          const failedRun = {
            run_id: "run-2",
            job_id: "run-2",
            document_id: "doc-1",
            attempt_number: 2,
            status: "failed",
            parser: "docling",
            pipeline: "vlm",
            source_file_name: "example.md",
            status_url: "/v1/ingest/runs/run-2",
            outputs_url: "/v1/ingest/runs/run-2/outputs",
            metadata: { requested_pipeline: "vlm" },
            error: "Pipeline IngestProgressVlmPipeline failed",
            created_at: "2026-01-01T00:01:00Z",
            updated_at: "2026-01-01T00:01:00Z",
          };
          const completedRun = {
            run_id: "run-1",
            job_id: "run-1",
            document_id: "doc-1",
            attempt_number: 1,
            status: "completed",
            parser: "docling",
            pipeline: "standard",
            source_file_name: "example.md",
            status_url: "/v1/ingest/runs/run-1",
            outputs_url: "/v1/ingest/runs/run-1/outputs",
            metadata: { pipeline: "standard" },
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          };
          return Promise.resolve(
            new Response(
              JSON.stringify({
                documents: [
                  {
                    document: {
                      document_id: "doc-1",
                      content_hash: "hash-1",
                      source_file_name: "example.md",
                      size_bytes: 9,
                      mime_type: "text/markdown",
                      created_at: "2026-01-01T00:00:00Z",
                      updated_at: "2026-01-01T00:01:00Z",
                    },
                    latest_run: uploadCount === 1 ? completedRun : failedRun,
                    runs: uploadCount === 1 ? [completedRun] : [failedRun, completedRun],
                  },
                ],
                failed: [],
              }),
              { status: 200, headers: { "Content-Type": "application/json" } },
            ),
          );
        }
        return fallbackFetch(input, init);
      }),
    );

    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["# Example"], "example.md", { type: "text/markdown" });

    await screen.findByText(".pdf, .md up to 100 MB");
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Ingest 1 file/ }));

    expect(await screen.findByText("example.md")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Pipeline"), { target: { value: "vlm" } });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Ingest 1 file/ }));

    await screen.findByText("Pipeline IngestProgressVlmPipeline failed");
    expect(screen.getAllByText("example.md")).toHaveLength(1);
    fireEvent.click(screen.getByText("Run history"));
    expect(screen.getByText("#2 vlm")).toBeInTheDocument();
    expect(screen.getByText("#1 standard")).toBeInTheDocument();
  });

  it("renders chunking toggle before parser-dependent strategy options", async () => {
    render(<App />);

    const chunkingToggle = await screen.findByRole("checkbox", { name: "Chunking" });
    expect(screen.queryByLabelText("Chunking strategy")).not.toBeInTheDocument();

    fireEvent.click(chunkingToggle);

    const chunkingStrategy = screen.getByLabelText("Chunking strategy");

    expect(chunkingToggle.compareDocumentPosition(chunkingStrategy)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(within(chunkingStrategy).getByRole("option", { name: "Token" })).toBeInTheDocument();
    expect(within(chunkingStrategy).getByRole("option", { name: "Page" })).toBeInTheDocument();
    expect(
      within(chunkingStrategy).queryByRole("option", { name: "Line" }),
    ).not.toBeInTheDocument();

    fireEvent.click(chunkingToggle);

    expect(screen.queryByLabelText("Chunking strategy")).not.toBeInTheDocument();
  });
});
