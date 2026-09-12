// @vitest-environment jsdom

import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useTheme } from "./use-theme";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;

function ThemeProbe() {
  const [theme] = useTheme();
  return <span data-theme-mode={theme}>{theme}</span>;
}

beforeEach(() => {
  window.localStorage.clear();
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn(() => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

afterEach(() => {
  act(() => root?.unmount());
  root = null;
  document.body.replaceChildren();
});

it("resets a prior-day theme preference to system", () => {
  window.localStorage.setItem("biosimulant.labsServe.theme", "light");
  window.localStorage.setItem(
    "biosimulant.labsServe.theme.preference-day",
    "2000-01-01",
  );
  const container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  act(() => root?.render(<ThemeProbe />));

  expect(container.textContent).toBe("system");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(window.localStorage.getItem("biosimulant.labsServe.theme")).toBe(
    "system",
  );
});
