import { describe, expect, it, vi } from "vitest";
import {
  isThemeMode,
  readStoredThemeMode,
  resolveThemeMode,
  THEME_STORAGE_KEY,
  writeStoredThemeMode,
} from "./theme";

describe("theme helpers", () => {
  it("resolves system mode from the media preference", () => {
    expect(resolveThemeMode("system", true)).toBe("dark");
    expect(resolveThemeMode("system", false)).toBe("light");
    expect(resolveThemeMode("light", true)).toBe("light");
    expect(resolveThemeMode("dark", false)).toBe("dark");
  });

  it("guards stored theme values", () => {
    expect(isThemeMode("system")).toBe(true);
    expect(isThemeMode("light")).toBe(true);
    expect(isThemeMode("dark")).toBe(true);
    expect(isThemeMode("sepia")).toBe(false);
  });

  it("reads and writes valid stored modes", () => {
    const storage = {
      value: "",
      getItem: vi.fn(() => "dark"),
      setItem: vi.fn((key: string, value: string) => {
        storage.value = `${key}:${value}`;
      }),
    };

    expect(readStoredThemeMode(storage)).toBe("dark");
    writeStoredThemeMode(storage, "light");
    expect(storage.setItem).toHaveBeenCalledWith(THEME_STORAGE_KEY, "light");
    expect(storage.value).toBe(`${THEME_STORAGE_KEY}:light`);
  });

  it("falls back to system for invalid storage", () => {
    expect(readStoredThemeMode({ getItem: () => "invalid" })).toBe("system");
  });
});
