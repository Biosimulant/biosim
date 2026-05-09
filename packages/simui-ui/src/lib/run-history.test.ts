import { describe, expect, it } from "vitest";
import {
  buildRunHistoryEntry,
  countVisuals,
  parseRunHistory,
  runStatusForHistory,
  serializeRunHistory,
} from "./run-history";

describe("run history helpers", () => {
  it("counts grouped visual entries", () => {
    expect(countVisuals([
      { module: "a", visuals: [{ render: "text", data: {} }] },
      { module: "b", visuals: [{ render: "bar", data: {} }, { render: "table", data: {} }] },
    ])).toBe(3);
  });

  it("derives terminal run status", () => {
    expect(runStatusForHistory({ running: false, paused: false })).toBe("completed");
    expect(runStatusForHistory({ running: false, paused: false, error: { message: "nope" } })).toBe("failed");
    expect(runStatusForHistory({ running: true, paused: false })).toBe("unknown");
  });

  it("builds and parses a session history entry", () => {
    const entry = buildRunHistoryEntry({
      id: "run-123",
      startedAt: new Date("2026-05-09T00:00:00Z"),
      finishedAt: new Date("2026-05-09T00:00:03Z"),
      status: { running: false, paused: false, step_count: 4 },
      visuals: [{ module: "model", visuals: [{ render: "text", data: { text: "done" } }] }],
      events: [{ id: 1, ts: "2026-05-09T00:00:01Z", event: "step" }],
    });

    expect(entry.status).toBe("completed");
    expect(entry.durationSeconds).toBe(3);
    expect(entry.stepCount).toBe(4);
    expect(entry.visualCount).toBe(1);

    const parsed = parseRunHistory(serializeRunHistory([entry]));
    expect(parsed).toHaveLength(1);
    expect(parsed[0]?.id).toBe("run-123");
  });

  it("ignores malformed history payloads", () => {
    expect(parseRunHistory("not json")).toEqual([]);
    expect(parseRunHistory(JSON.stringify({ id: "x" }))).toEqual([]);
  });
});
