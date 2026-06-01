import { describe, expect, it } from "vitest";

import {
  formatBytes,
  parserRetryMessage,
  phaseState,
  progressPercent,
  statusLabel,
} from "./status";
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
    expect(phaseState("retrying", "retrying")).toBe("active");
  });

  it("formats labels and bytes for compact UI cells", () => {
    expect(statusLabel("dispatch_queued")).toBe("dispatch queued");
    expect(statusLabel("retrying")).toBe("retrying parser");
    expect(formatBytes(1536)).toBe("1.5 KB");
  });

  it("describes parser retry metadata", () => {
    const job = {
      metadata: {
        parser_retry: {
          state: "retrying",
          failure_count: 2,
          max_retries: 3,
          last_error: "parse failed",
        },
      },
    } as unknown as IngestionJob;

    expect(parserRetryMessage(job)).toBe(
      "Retrying after parser error 2/3: parse failed",
    );
  });
});
