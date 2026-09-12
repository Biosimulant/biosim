import * as React from "react";

export type ThemeMode = "light" | "dark" | "system";

const THEME_KEY = "biosimulant.labsServe.theme";
const THEME_DAY_KEY = "biosimulant.labsServe.theme.preference-day";

function localDayKey(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function readTheme(): ThemeMode {
  if (window.localStorage.getItem(THEME_DAY_KEY) !== localDayKey()) {
    return "system";
  }
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
    window.localStorage.setItem(THEME_DAY_KEY, localDayKey());

    if (theme !== "system") return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleSystemThemeChange = () => applyTheme("system");
    mediaQuery.addEventListener?.("change", handleSystemThemeChange);
    return () => mediaQuery.removeEventListener?.("change", handleSystemThemeChange);
  }, [theme]);
  return [theme, setTheme];
}
