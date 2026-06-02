// @vitest-environment jsdom

import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import type { LocalLab } from "../types";
import { PreRunModal } from "./pre-run-modal";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let cleanup: (() => void) | null = null;

afterEach(() => {
  cleanup?.();
  cleanup = null;
});

it("submits settle steps from labs-serve pre-run runtime", () => {
  const onSubmit = vi.fn();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const lab = {
    manifest: {
      runtime: {
        duration: 10,
        communication_step: 0.5,
        settle_steps: 1,
      },
      io: { inputs: [], outputs: [] },
      models: [],
    },
  } as unknown as LocalLab;

  act(() => {
    root.render(
      <PreRunModal
        lab={lab}
        busy={false}
        onCancel={() => undefined}
        onSubmit={onSubmit}
      />,
    );
  });

  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  const button = Array.from(container.querySelectorAll("button")).find((candidate) =>
    candidate.textContent?.includes("Start run"),
  );
  expect(button).toBeInstanceOf(HTMLButtonElement);

  act(() => {
    button!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  expect(onSubmit).toHaveBeenCalledWith({
    parameters: { initial_inputs: {}, per_model: {} },
    simulation_config: {
      duration: 10,
      communication_step: 0.5,
      settle_steps: 1,
    },
  });
});
