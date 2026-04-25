import { describe, expect, it } from "vitest";

import { resolveRunProgress } from "./progress";

describe("resolveRunProgress", () => {
  it("prefers backend progress fields", () => {
    const out = resolveRunProgress({
      status: {
        running: true,
        paused: false,
        progress: 0.3,
        progress_pct: 30.0,
        sim_time: 3,
        sim_remaining: 7,
      },
      duration: 10,
    });
    expect(out.progress).toBe(0.3);
    expect(out.progressPct).toBe(30.0);
    expect(out.progressLabel).toBe("30.0%");
    expect(out.simTime).toBe(3);
    expect(out.simRemaining).toBe(7);
    expect(out.estimated).toBe(false);
  });

  it("clamps invalid percent ranges", () => {
    const high = resolveRunProgress({
      status: { running: true, paused: false, progress_pct: 120 },
      duration: 10,
    });
    expect(high.progress).toBe(1);
    expect(high.progressPct).toBe(100);

    const low = resolveRunProgress({
      status: { running: true, paused: false, progress_pct: -4 },
      duration: 10,
    });
    expect(low.progress).toBe(0);
    expect(low.progressPct).toBe(0);
  });

  it("returns unknown progress when neither backend nor fallback is usable", () => {
    const out = resolveRunProgress({
      status: { running: false, paused: false },
      duration: Number.NaN,
    });
    expect(out.progress).toBeNull();
    expect(out.progressPct).toBeNull();
    expect(out.progressLabel).toBe("—");
  });
});
