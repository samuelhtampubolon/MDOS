/* End-to-end tests: start the real server (desktop mode, fresh data folder) and drive the built app in Chromium.
   Run: npm run build && npm run e2e   (set PW_CHROMIUM_PATH to use a preinstalled Chromium). */

import { defineConfig, devices } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PORT = Number(process.env.MDOS_E2E_PORT ?? 8765);
// Workers load this file again and inherit the environment, so values created here are stored in it once.
if (!process.env.MDOS_E2E_DATA) {
  process.env.MDOS_E2E_DATA = mkdtempSync(join(tmpdir(), "mdos-e2e-"));
  process.env.MDOS_E2E_DATA_CREATED = "1"; // removed again by the global teardown
}
process.env.MDOS_E2E_KEY ??= randomBytes(32).toString("base64url"); // the per-launch key the desktop app would create
const dataDir = process.env.MDOS_E2E_DATA;
const python = process.env.MDOS_PYTHON
  ?? (process.env.CI ? "python" : process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");

export default defineConfig({
  testDir: "e2e",
  globalTeardown: "./e2e/teardown.ts",
  timeout: 300_000,
  expect: { timeout: 20_000 },
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
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
    command: `${python} -m mdos.desktop --no-browser --strict-port --port ${PORT} --data-dir "${dataDir}"`,
    cwd: "../backend",
    url: `http://127.0.0.1:${PORT}/api/health`,
    env: { MDOS_LOCAL_KEY: process.env.MDOS_E2E_KEY, RATE_LIMIT_AUTH_PER_MINUTE: "600" },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
