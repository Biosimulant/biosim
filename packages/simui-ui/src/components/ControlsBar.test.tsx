import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockState: any = {
  status: { running: false, paused: false },
  controls: { duration: 10 },
  spec: {
    controls: [{ type: "number", name: "duration", default: 10 }],
    capabilities: {},
  },
};

const mockActions = {
  setControls: vi.fn(),
};

vi.mock("../app/ui", () => ({
  useUi: () => ({ state: mockState, actions: mockActions }),
  useModuleNames: () => [],
  isNumberControl: (control: any) => control?.type === "number",
  isJsonControl: (control: any) => control?.type === "json",
}));

import ControlsBar from "./ControlsBar";

beforeEach(() => {
  mockActions.setControls.mockReset();
  mockState.status = { running: false, paused: false };
  mockState.controls = { duration: 10 };
  mockState.spec = {
    controls: [{ type: "number", name: "duration", default: 10 }],
    capabilities: {},
  };
});

describe("ControlsBar progress", () => {
  it("renders backend progress when available", () => {
    mockState.status = {
      running: true,
      paused: false,
      progress_pct: 25,
      sim_time: 2.5,
      step_count: 5,
    };

    const html = renderToStaticMarkup(
      <ControlsBar onRun={() => {}} onPause={() => {}} onResume={() => {}} onReset={() => {}} />,
    );

    expect(html).toContain("25.0%");
    expect(html).toContain("controls-bar-progress");
  });

  it("shows unknown progress when backend progress is missing", () => {
    mockState.status = {
      running: true,
      paused: false,
      step_count: 50,
    };
    mockState.controls = { duration: 10 };

    const html = renderToStaticMarkup(
      <ControlsBar onRun={() => {}} onPause={() => {}} onResume={() => {}} onReset={() => {}} />,
    );

    expect(html).toContain("—");
  });
});
