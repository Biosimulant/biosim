import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const root = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root,
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      all: true,
      include: ["src/lib/api.ts", "src/lib/config.ts", "src/lib/time.ts"],
      exclude: ["**/*.d.ts", "src/**/__tests__/**", "src/**/*.test.{ts,tsx}"],
    },
  },
});
