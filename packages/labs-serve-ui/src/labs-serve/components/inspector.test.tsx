// @vitest-environment jsdom

import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import type { LabModelEntry, LocalLab } from "../types";
import { Inspector } from "./inspector";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let cleanup: (() => void) | null = null;

afterEach(() => {
  cleanup?.();
  cleanup = null;
});

function renderInspector(lab: LocalLab, onSaveWorld = vi.fn()) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  act(() => {
    root.render(
      <Inspector
        lab={lab}
        selection={{ kind: "model", id: "target" }}
        onClose={() => undefined}
        onSaveWorld={onSaveWorld}
      />,
    );
  });

  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  return container;
}

it("renders model interface as read-only without wiring controls or saved default notices", () => {
  const onSaveWorld = vi.fn().mockResolvedValue(undefined);
  const lab = {
    id: "lab",
    title: "Lab",
    description: null,
    tags: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    manifest: {
      runtime: { initial_inputs: { target: { value: 5 } } },
      wiring: [],
      models: [
        {
          alias: "source",
          resolved_model: { io: { inputs: [], outputs: [{ name: "count" }] } },
        },
        {
          alias: "target",
          resolved_model: { io: { inputs: [{ name: "value" }], outputs: [] } },
        },
      ],
    },
  } as LocalLab;

  const container = renderInspector(lab, onSaveWorld);

  expect(container.querySelector('input[placeholder="Manual value"]')).toBeNull();
  expect(container.textContent).not.toContain("saved input default");
  expect(container.textContent).not.toContain("Connect source");
  expect(container.textContent).not.toContain("Connect target");
  expect(container.querySelector("select")).toBeNull();

  const sectionTitles = Array.from(container.querySelectorAll(".property-collapse-header")).map(
    (button) => button.textContent ?? "",
  );
  expect(sectionTitles.some((title) => title.includes("Inputs"))).toBe(false);
  expect(sectionTitles.some((title) => title.includes("Outputs"))).toBe(false);
  expect(sectionTitles.some((title) => title.includes("Interface"))).toBe(true);
  expect(container.textContent).toContain("value");
  expect(onSaveWorld).not.toHaveBeenCalled();
});

function worldModel(alias: string, inputs: string[] = [], outputs: string[] = []): LabModelEntry {
  return {
    alias,
    resolved_model: {
      title: alias,
      io: {
        inputs: inputs.map((name) => ({ name })),
        outputs: outputs.map((name) => ({ name })),
      },
    },
  };
}

function makeWorldLab(overrides: Partial<LocalLab["manifest"]> = {}): LocalLab {
  return {
    id: "lab-1",
    title: "Serve Lab",
    description: "Local serve lab",
    tags: [],
    manifest: {
      models: [],
      children: [],
      wiring: [],
      runtime: { duration: 10, communication_step: 0.1 },
      io: { inputs: [], outputs: [] },
      ...overrides,
    },
    wiring_layout: null,
    created_at: "2026-06-03T00:00:00Z",
    updated_at: "2026-06-03T00:00:00Z",
  };
}

function renderWorldInspector(lab: LocalLab, onSaveWorld = vi.fn()) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(
      <Inspector
        lab={lab}
        selection={{ kind: "world" }}
        onClose={() => undefined}
        onSaveWorld={onSaveWorld}
      />,
    );
  });
  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };
  return container;
}

function clickElement(element: Element) {
  act(() => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

async function setSelectValue(select: HTMLSelectElement, value: string) {
  await act(async () => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await Promise.resolve();
  });
}

function openConnections(container: HTMLElement) {
  const button = Array.from(container.querySelectorAll<HTMLButtonElement>(".property-collapse-header"))
    .find((candidate) => candidate.textContent?.includes("Connections"));
  expect(button).toBeInstanceOf(HTMLButtonElement);
  clickElement(button!);
}

it("renders world connections and flattens fan-out wiring", () => {
  const lab = makeWorldLab({
    wiring: [
      { from: "source.signal", to: ["target.input", "other.input"] },
      { source: "legacy.out", target: "target.legacy" },
    ],
  });
  const container = renderWorldInspector(lab);

  openConnections(container);

  expect(container.textContent).toContain("source.signal");
  expect(container.textContent).toContain("target.input");
  expect(container.textContent).toContain("other.input");
  expect(container.textContent).toContain("legacy.out");
  expect(container.textContent).toContain("target.legacy");
});

it("shows saved input default compatibility notice on the world inspector", () => {
  const lab = makeWorldLab({
    runtime: {
      duration: 10,
      communication_step: 0.1,
      initial_inputs: { target: { value: 5, other: 2 } },
    },
  });
  const container = renderWorldInspector(lab);

  expect(container.textContent).toContain("2 saved input defaults");
});

it("adds a world-level connection after source and target are selected", async () => {
  const onSaveWorld = vi.fn(async () => undefined);
  const lab = makeWorldLab({
    models: [worldModel("source", [], ["signal"]), worldModel("target", ["input"], [])],
  });
  const container = renderWorldInspector(lab, onSaveWorld);

  openConnections(container);
  clickElement(container.querySelector('button[aria-label="Add world connection"]')!);
  await setSelectValue(
    container.querySelector<HTMLSelectElement>('select[aria-label="Draft connection 1 source"]')!,
    "source.signal",
  );
  await setSelectValue(
    container.querySelector<HTMLSelectElement>('select[aria-label="Draft connection 1 target"]')!,
    "target.input",
  );

  expect(onSaveWorld).toHaveBeenCalledWith({
    wiring: [{ from: "source.signal", to: "target.input" }],
  });
});

it("removes a world-level connection", () => {
  const onSaveWorld = vi.fn(async () => undefined);
  const lab = makeWorldLab({
    wiring: [{ from: "source.signal", to: "target.input" }],
  });
  const container = renderWorldInspector(lab, onSaveWorld);

  openConnections(container);
  clickElement(
    container.querySelector<HTMLButtonElement>(
      'button[aria-label="Remove connection source.signal to target.input"]',
    )!,
  );

  expect(onSaveWorld).toHaveBeenCalledWith({ wiring: [] });
});

it("excludes same-alias targets in draft world connections", async () => {
  const onSaveWorld = vi.fn(async () => undefined);
  const lab = makeWorldLab({
    models: [
      worldModel("source", ["self_input"], ["signal"]),
      worldModel("target", ["input"], []),
    ],
  });
  const container = renderWorldInspector(lab, onSaveWorld);

  openConnections(container);
  clickElement(container.querySelector('button[aria-label="Add world connection"]')!);
  await setSelectValue(
    container.querySelector<HTMLSelectElement>('select[aria-label="Draft connection 1 source"]')!,
    "source.signal",
  );

  const targetOptions = Array.from(
    container.querySelectorAll<HTMLOptionElement>(
      'select[aria-label="Draft connection 1 target"] option',
    ),
  ).map((option) => option.value);
  expect(targetOptions).toContain("target.input");
  expect(targetOptions).not.toContain("source.self_input");
  expect(onSaveWorld).not.toHaveBeenCalled();
});

it("does not save duplicate world connections", async () => {
  const onSaveWorld = vi.fn(async () => undefined);
  const lab = makeWorldLab({
    models: [worldModel("source", [], ["signal"]), worldModel("target", ["input"], [])],
    wiring: [{ from: "source.signal", to: "target.input" }],
  });
  const container = renderWorldInspector(lab, onSaveWorld);

  openConnections(container);
  clickElement(container.querySelector('button[aria-label="Add world connection"]')!);
  await setSelectValue(
    container.querySelector<HTMLSelectElement>('select[aria-label="Draft connection 1 source"]')!,
    "source.signal",
  );
  await setSelectValue(
    container.querySelector<HTMLSelectElement>('select[aria-label="Draft connection 1 target"]')!,
    "target.input",
  );

  expect(onSaveWorld).not.toHaveBeenCalled();
});
