import { describe, expect, it } from "vitest";

import { formatDuration } from "./time";

describe("formatDuration", () => {
  it("formats invalid and bounded values", () => {
    expect(formatDuration(Number.NaN)).toBe("—");
    expect(formatDuration(-1)).toBe("0s");
  });

  it("formats seconds, minutes, and hours", () => {
    expect(formatDuration(12)).toBe("12s");
    expect(formatDuration(65)).toBe("1m 5s");
    expect(formatDuration(3661)).toBe("1h 1m 1s");
  });
});
