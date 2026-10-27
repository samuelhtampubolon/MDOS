/// <reference types="vitest" />
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// The live demo runs the whole app in the browser, so its page carries the policy a server would send. Python
// (Pyodide) needs 'wasm-unsafe-eval' to compile WebAssembly; nothing is loaded from other sites.
const DEMO_CSP = [
  "default-src 'self'", "script-src 'self' 'wasm-unsafe-eval'", "worker-src 'self'", "style-src 'self'",
  "img-src 'self' data: blob:", "font-src 'self' data:", "connect-src 'self'", "object-src 'none'",
  "base-uri 'self'", "form-action 'none'",
].join("; ");

function demoPage(): Plugin {
  return {
    name: "mdos-demo-page",
    transformIndexHtml: (html) => html
      .replace(`<meta charset="UTF-8" />`, `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${DEMO_CSP}" />\n    <meta name="referrer" content="no-referrer" />`)
      .replace("<title>Marketing Decision OS</title>", "<title>MDOS live demo</title>"),
  };
}

// Development: the API runs on :8000 and Vite proxies /api to it.
// Production: the build is written into the Python package so one process serves both.
// Demo (`vite build --mode demo`): a static build for GitHub Pages whose API runs in the browser (src/demo).
export default defineConfig(({ mode }) => {
  const isDemo = mode === "demo";
  return {
    plugins: isDemo ? [react(), demoPage()] : [react()],
    base: isDemo ? "./" : "/",
    resolve: {
      alias: isDemo
        ? [{ find: /^(\.{1,2}\/)+(api\/)?transport$/, replacement: fileURLToPath(new URL("./src/demo/transport.ts", import.meta.url)) }]
        : [],
    },
    worker: { format: "es" },
    server: {
      port: 5173,
      proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
    },
    // The demo has no server: its preview must not forward /api anywhere (server.proxy would be reused otherwise).
    preview: isDemo ? { proxy: {} } : undefined,
    build: {
      outDir: isDemo ? "dist-demo" : "../backend/mdos/static",
      emptyOutDir: true,
      chunkSizeWarningLimit: 900,
    },
    test: { environment: "node", include: ["src/**/*.test.ts"] },
  };
});
