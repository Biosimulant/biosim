// @vitest-environment jsdom

import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it } from "vitest";
import { UpgradeBanner } from "./App";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let cleanup: (() => void) | null = null;
let storedItems: Record<string, string> = {};

Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: {
    clear: () => {
      storedItems = {};
    },
    getItem: (key: string) => storedItems[key] ?? null,
    setItem: (key: string, value: string) => {
      storedItems[key] = value;
    },
  },
});

afterEach(() => {
  cleanup?.();
  cleanup = null;
  window.localStorage.clear();
});

function renderBanner() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  act(() => {
    root.render(<UpgradeBanner />);
  });

  const unmount = () => {
    act(() => root.unmount());
    container.remove();
  };
  cleanup = unmount;

  return { container, unmount };
}

it("dismisses the desktop app banner only until the page is reloaded", () => {
  window.localStorage.setItem("biosimulant.labsServe.upgradeDismissed", "1");

  const firstRender = renderBanner();
  expect(firstRender.container.textContent).toContain("get the desktop app");

  const dismiss = firstRender.container.querySelector(".upgrade-banner-dismiss");
  expect(dismiss).toBeInstanceOf(HTMLButtonElement);

  act(() => {
    dismiss!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });

  expect(firstRender.container.textContent).not.toContain("get the desktop app");

  firstRender.unmount();
  cleanup = null;

  const secondRender = renderBanner();
  expect(secondRender.container.textContent).toContain("get the desktop app");
  expect(window.localStorage.getItem("biosimulant.labsServe.upgradeDismissed")).toBe("1");
});
