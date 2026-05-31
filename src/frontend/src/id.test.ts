import { afterEach, describe, expect, it, vi } from "vitest";

import { createLocalId } from "./id";

const originalCrypto = globalThis.crypto;

describe("createLocalId", () => {
  afterEach(() => {
    Object.defineProperty(globalThis, "crypto", {
      value: originalCrypto,
      configurable: true,
    });
    vi.restoreAllMocks();
  });

  it("uses crypto.randomUUID when available", () => {
    Object.defineProperty(globalThis, "crypto", {
      value: { randomUUID: () => "uuid-from-browser" },
      configurable: true,
    });

    expect(createLocalId()).toBe("uuid-from-browser");
  });

  it("falls back to crypto.getRandomValues when randomUUID is unavailable", () => {
    Object.defineProperty(globalThis, "crypto", {
      value: {
        getRandomValues: (array: Uint8Array) => {
          array.set(Array.from({ length: 16 }, (_, index) => index));
          return array;
        },
      },
      configurable: true,
    });

    expect(createLocalId()).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
  });

  it("falls back to timestamp and Math.random without browser crypto", () => {
    vi.spyOn(Date, "now").mockReturnValue(123456789);
    vi.spyOn(Math, "random").mockReturnValue(0.123456789);
    Object.defineProperty(globalThis, "crypto", {
      value: undefined,
      configurable: true,
    });

    expect(createLocalId()).toBe("21i3v9-4fzzzxjylr");
  });
});
