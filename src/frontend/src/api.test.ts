import { describe, expect, it } from "vitest";

import { buildIngestQuery } from "./api";
import type { IngestionOptions } from "./types";

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
