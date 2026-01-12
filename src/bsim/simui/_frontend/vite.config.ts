import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Ensure single-file JS bundle named app.js to satisfy Python build step
export default defineConfig({
  plugins: [react()],
  build: {
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'app.js',
        assetFileNames: 'app.[ext]',
        inlineDynamicImports: true,
        manualChunks: undefined
      }
    }
  },
  test: {
    environment: 'jsdom'
  }
})
