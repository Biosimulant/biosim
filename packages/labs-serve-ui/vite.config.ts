import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    emptyOutDir: true,
    outDir: "../../src/biosim/labs_serve/static",
    rollupOptions: {
      input: path.resolve(__dirname, "index.html"),
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
        manualChunks: {
          canvas: ["@xyflow/react", "dagre"],
          icons: ["lucide-react"]
        }
      }
    }
  },
  test: {
    environment: "jsdom"
  }
});
