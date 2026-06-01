import { afterEach, describe, expect, it, vi } from "vitest";

import { buildIngestQuery, getJobs, getQueueMetrics } from "./api";
import type { IngestionOptions } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("buildIngestQuery", () => {
  it("serializes every upload option supported by the API", () => {
    const options: IngestionOptions = {
      parser: "docling",
      pipeline: "vlm",
      chunkingEnabled: false,
      chunkingStrategy: "line_based",
      dispatchSinkMode: "elastic",
      ocrLanguages: ["es", "en"],
      asyncMode: true,
      includeDocument: false,
      includeHtml: true,
    };

    const params = new URLSearchParams(buildIngestQuery(options));

    expect(params.get("parser")).toBe("docling");
    expect(params.get("pipeline")).toBe("vlm");
    expect(params.get("chunking_enabled")).toBe("false");
    expect(params.get("chunking_strategy")).toBe("line_based");
    expect(params.get("dispatch_sink_mode")).toBe("elastic");
    expect(params.get("ocr_languages")).toBe("es,en");
    expect(params.get("async_mode")).toBe("true");
    expect(params.get("include_document")).toBe("false");
    expect(params.get("include_html")).toBe("true");
  });
});

describe("getQueueMetrics", () => {
  it("requests bounded queue metrics", async () => {
    const fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          queue_backend: "local",
          parser_queue_name: "parser",
          dispatch_queue_name: "dispatch",
          parser_worker_count: 2,
          dispatch_worker_count: 2,
          status_counts: {},
          stages: [],
          dispatch_queue: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });
    vi.stubGlobal("fetch", fetch);

    await getQueueMetrics("http://api.test", 10);

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/v1/ingest/queue/metrics?limit=10",
      undefined,
    );
  });
});

describe("getJobs", () => {
  it("requests active jobs in one batch", async () => {
    const fetch = vi.fn(async () => {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetch);

    await getJobs(["job-1", "job-2"], "http://api.test");

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/v1/ingest/jobs?ids=job-1%2Cjob-2",
      undefined,
    );
  });
});
