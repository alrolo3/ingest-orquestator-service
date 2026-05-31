import { describe, expect, it } from "vitest";

import { formatBytes, phaseState, progressPercent, statusLabel } from "./status";
import type { IngestionJob } from "./types";

describe("status helpers", () => {
  it("uses Docling page progress during parsing", () => {
    const job = {
      status: "parsing",
      metadata: {
        progress: {
          page_count: 10,
          pages_completed: 5,
          percent_complete: 50,
        },
      },
    } as unknown as IngestionJob;

    expect(progressPercent(job)).toBe(43);
  });

  it("maps phase state from lifecycle order", () => {
    expect(phaseState("parser_queued", "dispatching")).toBe("done");
    expect(phaseState("dispatching", "dispatching")).toBe("active");
    expect(phaseState("completed", "dispatching")).toBe("pending");
  });

  it("formats labels and bytes for compact UI cells", () => {
    expect(statusLabel("dispatch_queued")).toBe("dispatch queued");
    expect(formatBytes(1536)).toBe("1.5 KB");
  });
});
