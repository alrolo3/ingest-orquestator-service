import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
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
            chunking: {
              enabled: true,
              default_strategy: "hybrid",
              strategies: [
                { value: "hybrid", label: "Hybrid" },
                { value: "line_based", label: "Line Based" },
              ],
            },
            runtime: {},
            output_types: ["manifest", "normalized", "chunks"],
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
});
