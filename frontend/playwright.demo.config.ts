/* End-to-end tests of the live demo: the static GitHub Pages build, with the MDOS server running in the browser.
   Run: npm run build:demo && python ../scripts/build_demo.py && npx playwright test -c playwright.demo.config.ts
   (set PW_CHROMIUM_PATH to use a preinstalled Chromium). */

import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.MDOS_DEMO_PORT ?? 8766);

export default defineConfig({
  testDir: "e2e-demo",
  timeout: 600_000,
  expect: { timeout: 60_000 },
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never", outputFolder: "playwright-report-demo" }]] : "list",
  outputDir: "test-results-demo",
  use: {
    baseURL: `http://127.0.0.1:${PORT}/`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{
    name: "chromium",
    use: {
      ...devices["Desktop Chrome"],
      viewport: { width: 1440, height: 950 },
      launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
    },
  }],
  webServer: {
    // Vite's preview server only serves the built files, like GitHub Pages.
    command: `npx vite preview --mode demo --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
