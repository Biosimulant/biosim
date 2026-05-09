import type { ResolvedTheme, ThemeMode } from "../types/shell";

export const THEME_STORAGE_KEY = "simui-theme-mode";

export function isThemeMode(value: unknown): value is ThemeMode {
  return value === "system" || value === "light" || value === "dark";
}

export function resolveThemeMode(mode: ThemeMode, prefersDark: boolean): ResolvedTheme {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode;
}

export function readStoredThemeMode(storage: Pick<Storage, "getItem"> | null | undefined): ThemeMode {
  try {
    const stored = storage?.getItem(THEME_STORAGE_KEY);
    return isThemeMode(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function writeStoredThemeMode(
  storage: Pick<Storage, "setItem"> | null | undefined,
  mode: ThemeMode,
): void {
  try {
    storage?.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // Ignore storage errors in private mode or embedded contexts.
  }
}
