import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildIngestQuery,
  defaultApiBaseUrl,
  deleteJob,
  getIngestorSettings,
  getJobs,
  getQueueMetrics,
  getRuns,
  updateIngestorSettings,
  uploadDocuments,
} from "./api";
import type { IngestionOptions } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("defaultApiBaseUrl", () => {
  it("uses same-origin API calls unless an explicit Vite env override is provided", () => {
    expect(defaultApiBaseUrl).toBe("");
  });
});

describe("buildIngestQuery", () => {
  it("serializes every upload option supported by the API", () => {
    const options: IngestionOptions = {
      parser: "docling",
      pipeline: "vlm",
      chunkingEnabled: false,
      chunkingStrategy: "page",
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
    expect(params.get("chunking_strategy")).toBeNull();
    expect(params.get("dispatch_sink_mode")).toBe("elastic");
    expect(params.get("ocr_languages")).toBe("es,en");
    expect(params.get("async_mode")).toBe("true");
    expect(params.get("include_document")).toBe("false");
    expect(params.get("include_html")).toBe("true");
  });

  it("serializes strategy only when request-level chunking is enabled", () => {
    const options: IngestionOptions = {
      parser: "docling",
      pipeline: "standard",
      chunkingEnabled: true,
      chunkingStrategy: "token",
      dispatchSinkMode: "local",
      ocrLanguages: [],
      asyncMode: false,
      includeDocument: true,
      includeHtml: false,
    };

    const params = new URLSearchParams(buildIngestQuery(options));

    expect(params.get("chunking_enabled")).toBe("true");
    expect(params.get("chunking_strategy")).toBe("token");
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
          parser_process_count: 2,
          parser_threads_per_process: 1,
          active_parser_job_count: 0,
          queued_parser_job_count: 0,
          stale_parser_job_count: 0,
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

describe("ingestor settings API", () => {
  it("loads persistent ingestor settings", async () => {
    const fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ fields: [], boot_time_keys: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetch);

    await getIngestorSettings("http://api.test");

    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ingest/settings", undefined);
  });

  it("patches changed ingestor setting values and resets", async () => {
    const fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ fields: [], boot_time_keys: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetch);

    await updateIngestorSettings(
      {
        values: { docling_accelerator_device: "cuda" },
        reset_keys: ["max_upload_size_mb"],
      },
      "http://api.test",
    );

    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ingest/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        values: { docling_accelerator_device: "cuda" },
        reset_keys: ["max_upload_size_mb"],
      }),
    });
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

describe("document run API", () => {
  it("uploads files through the document endpoint", async () => {
    const fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ documents: [], failed: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetch);

    const file = new File(["# Example"], "example.md", { type: "text/markdown" });
    const options: IngestionOptions = {
      parser: "docling",
      pipeline: "standard",
      chunkingEnabled: false,
      chunkingStrategy: "page",
      dispatchSinkMode: "local",
      ocrLanguages: [],
      asyncMode: false,
      includeDocument: true,
      includeHtml: false,
    };

    await uploadDocuments([file], options, "http://api.test");

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/v1/ingest/documents?parser=docling&pipeline=standard&chunking_enabled=false&dispatch_sink_mode=local&async_mode=false&include_document=true&include_html=false",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("polls active runs in one batch", async () => {
    const fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ runs: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetch);

    await getRuns(["run-1", "run-2"], "http://api.test");

    expect(fetch).toHaveBeenCalledWith(
      "http://api.test/v1/ingest/runs?ids=run-1%2Crun-2",
      undefined,
    );
  });
});

describe("deleteJob", () => {
  it("requests job removal", async () => {
    const fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          job_id: "job-1",
          previous_status: "parser_queued",
          removed: true,
          parser_process_terminated: false,
          removed_dispatch_queue_item: false,
          removed_artifact_count: 0,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });
    vi.stubGlobal("fetch", fetch);

    await deleteJob("job-1", "http://api.test");

    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ingest/jobs/job-1", {
      method: "DELETE",
    });
  });
});
