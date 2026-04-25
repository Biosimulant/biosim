import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockState: any = {
  status: { running: false, paused: false },
  controls: { duration: 10 },
  visibleModules: new Set<string>(),
  spec: {
    controls: [{ type: "number", name: "duration", default: 10 }],
    modules: [],
    capabilities: {},
  },
};

const mockActions = {
  setControls: vi.fn(),
  setVisibleModules: vi.fn(),
};

vi.mock("../app/ui", () => ({
  useUi: () => ({ state: mockState, actions: mockActions }),
  useModuleNames: () => [],
  isNumberControl: (control: any) => control?.type === "number",
  isJsonControl: (control: any) => control?.type === "json",
}));

import Sidebar from "./Sidebar";

beforeEach(() => {
  mockActions.setControls.mockReset();
  mockActions.setVisibleModules.mockReset();
  mockState.status = { running: false, paused: false };
  mockState.controls = { duration: 10 };
  mockState.spec = {
    controls: [{ type: "number", name: "duration", default: 10 }],
    modules: [],
    capabilities: {},
  };
});

describe("Sidebar ActionsBar", () => {
  it("renders disabled run button with reason and sidebar action when run is blocked", () => {
    mockState.spec.capabilities = {
      controls: false,
      run: false,
      showRunWhenDisabled: true,
      runDisabledReason: "Fork this space to run it.",
      pauseResume: false,
      reset: false,
    };

    const html = renderToStaticMarkup(
      <Sidebar
        onRun={() => {}}
        onPause={() => {}}
        onResume={() => {}}
        onReset={() => {}}
        sidebarAction={<button type="button">Fork Space</button>}
      />,
    );

    expect(html).toContain("Run Simulation");
    expect(html).toContain("Fork Space");
    expect(html).toContain("title=\"Fork this space to run it.\"");
    expect(html).toContain("disabled");
  });

  it("hides run button when run is disabled and showRunWhenDisabled is false", () => {
    mockState.spec.capabilities = {
      controls: false,
      run: false,
      showRunWhenDisabled: false,
      pauseResume: false,
      reset: false,
    };

    const html = renderToStaticMarkup(
      <Sidebar onRun={() => {}} onPause={() => {}} onResume={() => {}} onReset={() => {}} />,
    );

    expect(html).not.toContain("Run Simulation");
  });

  it("shows running progress in status summary", () => {
    mockState.status = { running: true, paused: false, progress_pct: 42, step_count: 42 };
    mockState.spec.controls = [
      { type: "number", name: "duration", default: 10 },
    ];

    const html = renderToStaticMarkup(
      <Sidebar onRun={() => {}} onPause={() => {}} onResume={() => {}} onReset={() => {}} />,
    );

    expect(html).toContain("Running · 42.0%");
  });

  it("keeps last run progress in idle status summary", () => {
    mockState.status = { running: false, paused: false, progress_pct: 68.5, step_count: 10 };
    mockState.spec.controls = [
      { type: "number", name: "duration", default: 10 },
    ];

    const html = renderToStaticMarkup(
      <Sidebar onRun={() => {}} onPause={() => {}} onResume={() => {}} onReset={() => {}} />,
    );

    expect(html).toContain("Idle · Last run: 68.5%");
  });
});
