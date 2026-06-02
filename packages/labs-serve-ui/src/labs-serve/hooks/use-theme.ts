import * as React from "react";

export type ThemeMode = "light" | "dark" | "system";

const THEME_KEY = "biosimulant.labsServe.theme";

function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem(THEME_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

function applyTheme(mode: ThemeMode) {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolved = mode === "system" ? (prefersDark ? "dark" : "light") : mode;
  document.documentElement.dataset.theme = resolved;
}

export function useTheme(): [ThemeMode, (next: ThemeMode) => void] {
  const [theme, setTheme] = React.useState<ThemeMode>(() => readTheme());
  React.useEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);
  return [theme, setTheme];
}
