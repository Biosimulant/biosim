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

  expect(container.querySelector(".modal-compute-warnings")).toBeNull();

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

it("submits world input values as ephemeral run overrides", () => {
  const onSubmit = vi.fn();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const lab = {
    manifest: {
      runtime: {},
      io: { inputs: [{ name: "seed", maps_to: "target.value" }], outputs: [] },
      models: [
        {
          alias: "target",
          resolved_model: { io: { inputs: [{ name: "value" }], outputs: [] } },
        },
      ],
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

  const worldInputsButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
    candidate.textContent?.includes("World Inputs"),
  );
  expect(worldInputsButton).toBeInstanceOf(HTMLButtonElement);

  act(() => {
    worldInputsButton!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  const input = container.querySelector(".modal-input-row-value");
  expect(input).toBeInstanceOf(HTMLInputElement);
  act(() => {
    const valueSetter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    valueSetter?.call(input, "4");
    input!.dispatchEvent(new Event("input", { bubbles: true }));
    input!.dispatchEvent(new Event("change", { bubbles: true }));
  });

  const submitButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
    candidate.textContent?.includes("Start run"),
  );
  expect(submitButton).toBeInstanceOf(HTMLButtonElement);

  act(() => {
    submitButton!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  expect(onSubmit).toHaveBeenCalledWith({
    parameters: { initial_inputs: { seed: 4 }, per_model: {} },
    simulation_config: {},
  });
});

it("shows compute warnings without blocking run submission", () => {
  const onSubmit = vi.fn();
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const lab = {
    compute_warnings: [
      {
        code: "gpu-accelerator-requested",
        message:
          "Model 'boltz' requests GPU acceleration via accelerator='gpu'; the run will continue.",
        model_alias: "boltz",
        parameter: "accelerator",
        value: "gpu",
      },
    ],
    manifest: {
      runtime: {
        duration: 10,
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

  const warning = container.querySelector(".modal-compute-warnings");
  expect(warning).toBeInstanceOf(HTMLDivElement);
  expect(warning?.textContent).toContain("requests GPU acceleration");

  const submitButton = Array.from(container.querySelectorAll("button")).find((candidate) =>
    candidate.textContent?.includes("Start run"),
  );
  expect(submitButton).toBeInstanceOf(HTMLButtonElement);

  act(() => {
    submitButton!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  expect(onSubmit).toHaveBeenCalledWith({
    parameters: { initial_inputs: {}, per_model: {} },
    simulation_config: {
      duration: 10,
    },
  });
});
