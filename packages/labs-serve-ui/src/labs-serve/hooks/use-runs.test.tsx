// @vitest-environment jsdom

import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import type { RunsState } from "./use-runs";
import { useRuns } from "./use-runs";
import type { RunStatus } from "../types";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let cleanup: (() => void) | null = null;

afterEach(() => {
  cleanup?.();
  cleanup = null;
  vi.restoreAllMocks();
});

function Harness({ onState }: { onState: (state: RunsState) => void }) {
  const state = useRuns();
  React.useEffect(() => {
    onState(state);
  }, [onState, state]);
  return null;
}

function runPayload(status: RunStatus) {
  return {
    id: `run-${status}`,
    lab_id: "lab",
    model_id: null,
    status,
    execution_target: "local",
    hub_run_id: null,
    parameters: null,
    simulation_config: null,
    results_summary: null,
    results_path: null,
    error_message: null,
    duration_seconds: status === "completed" ? 1.2 : null,
    progress: status === "running" || status === "cancelling" ? { progress_pct: 25 } : { progress_pct: 100 },
    started_at: "2026-06-03T00:00:00Z",
    completed_at: status === "completed" ? "2026-06-03T00:00:01Z" : null,
    created_at: "2026-06-03T00:00:00Z",
  };
}

it("does not fetch results while the selected run is active", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path === "/api/runs") {
      return Response.json({ ok: true, data: { runs: [runPayload("running")] }, error: null });
    }
    if (path === "/api/runs/run-running") {
      return Response.json({ ok: true, data: { run: runPayload("running") }, error: null });
    }
    if (path === "/api/runs/run-running/logs") {
      return Response.json({ ok: true, data: { logs: [] }, error: null });
    }
    if (path === "/api/runs/run-running/results") {
      throw new Error("active run should not fetch results");
    }
    throw new Error(`unexpected fetch ${path}`);
  });

  const states: RunsState[] = [];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(<Harness onState={(state) => states.push(state)} />);
  });

  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  await act(async () => {
    await Promise.resolve();
  });

  expect(fetchMock).not.toHaveBeenCalledWith("/api/runs/run-running/results", expect.anything());
  expect(states.at(-1)?.selectedRun?.status).toBe("running");
  expect(states.at(-1)?.results).toBeNull();
});

it("treats a cancelling run as active", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path === "/api/runs") {
      return Response.json({ ok: true, data: { runs: [runPayload("cancelling")] }, error: null });
    }
    if (path === "/api/runs/run-cancelling") {
      return Response.json({ ok: true, data: { run: runPayload("cancelling") }, error: null });
    }
    if (path === "/api/runs/run-cancelling/logs") {
      return Response.json({ ok: true, data: { logs: [] }, error: null });
    }
    if (path === "/api/runs/run-cancelling/results") {
      throw new Error("cancelling run should not fetch results");
    }
    throw new Error(`unexpected fetch ${path}`);
  });

  const states: RunsState[] = [];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(<Harness onState={(state) => states.push(state)} />);
  });

  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  await act(async () => {
    await Promise.resolve();
  });

  expect(fetchMock).not.toHaveBeenCalledWith("/api/runs/run-cancelling/results", expect.anything());
  expect(states.at(-1)?.activeRun?.status).toBe("cancelling");
  expect(states.at(-1)?.results).toBeNull();
});

it("fetches results once the selected run is complete", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path === "/api/runs") {
      return Response.json({ ok: true, data: { runs: [runPayload("completed")] }, error: null });
    }
    if (path === "/api/runs/run-completed") {
      return Response.json({ ok: true, data: { run: runPayload("completed") }, error: null });
    }
    if (path === "/api/runs/run-completed/logs") {
      return Response.json({ ok: true, data: { logs: [] }, error: null });
    }
    if (path === "/api/runs/run-completed/results") {
      return Response.json({
        ok: true,
        data: { results: { visuals: [{ module: "core", visuals: [] }] } },
        error: null,
      });
    }
    throw new Error(`unexpected fetch ${path}`);
  });

  const states: RunsState[] = [];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(<Harness onState={(state) => states.push(state)} />);
  });

  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  await act(async () => {
    await Promise.resolve();
  });

  expect(states.at(-1)?.selectedRun?.status).toBe("completed");
  expect(states.at(-1)?.results?.visuals?.[0]?.module).toBe("core");
});

it("surfaces create-run conflict errors", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === "/api/runs" && init?.method === "POST") {
      return Response.json(
        {
          ok: false,
          data: null,
          error: { message: "Run run-active is already running" },
        },
        { status: 409 },
      );
    }
    if (path === "/api/runs") {
      return Response.json({ ok: true, data: { runs: [] }, error: null });
    }
    throw new Error(`unexpected fetch ${path}`);
  });

  const states: RunsState[] = [];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(<Harness onState={(state) => states.push(state)} />);
  });

  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  await act(async () => {
    await Promise.resolve();
  });

  await act(async () => {
    await expect(states.at(-1)!.startRun()).rejects.toThrow("Run run-active is already running");
  });

  expect(states.at(-1)?.error).toBe("Run run-active is already running");
});
