import { afterEach, describe, expect, it, vi } from "vitest";

import { buildIngestQuery, getJobs } from "./api";
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
      asyncMode: true,
      includeDocument: false,
    };

    const params = new URLSearchParams(buildIngestQuery(options));

    expect(params.get("parser")).toBe("docling");
    expect(params.get("pipeline")).toBe("vlm");
    expect(params.get("chunking_enabled")).toBe("false");
    expect(params.get("chunking_strategy")).toBe("line_based");
    expect(params.get("async_mode")).toBe("true");
    expect(params.get("include_document")).toBe("false");
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

    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ingest/jobs?ids=job-1%2Cjob-2", undefined);
  });
});
