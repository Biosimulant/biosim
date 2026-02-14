import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const isLibrary = mode === "library";

  if (isLibrary) {
    return {
      plugins: [react()],
      build: {
        outDir: "dist",
        emptyOutDir: true,
        sourcemap: true,
        lib: {
          entry: path.resolve(__dirname, "src/index.ts"),
          formats: ["es", "cjs"],
          fileName: (format) => (format === "es" ? "index.js" : "index.cjs"),
        },
        rollupOptions: {
          external: ["react", "react-dom", "react/jsx-runtime"],
          output: {
            exports: "named",
          },
        },
      },
      test: {
        environment: "jsdom",
      },
    };
  }

  return {
    plugins: [react()],
    build: {
      outDir: "dist-static",
      emptyOutDir: true,
      cssCodeSplit: false,
      rollupOptions: {
        output: {
          entryFileNames: "app.js",
          chunkFileNames: "app.js",
          assetFileNames: "app.[ext]",
          inlineDynamicImports: true,
          manualChunks: undefined,
        },
      },
    },
    test: {
      environment: "jsdom",
    },
  };
});
