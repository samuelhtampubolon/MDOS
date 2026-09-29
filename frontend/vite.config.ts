/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Development: the API runs on :8000 and Vite proxies /api to it.
// Production: the build is written into the Python package so one process serves both.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: {
    outDir: "../backend/mdos/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
