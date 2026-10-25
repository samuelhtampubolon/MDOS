// MDOS, Marketing Decision OS. Copyright © 2026 Samuel Hasudungan Tampubolon. Released under the MIT License.
//
// Prepares the built web app (frontend/dist) for a static host that sits in front of the MDOS backend.
// The host serves the interface and forwards /api/* to the backend, so the browser sees one site and the
// session cookie keeps its SameSite=Strict and __Host- protections.
//
//   MDOS_BACKEND_URL=https://your-space.hf.space npm run build:dist && node scripts/static-host.mjs netlify
//
// Hosts: netlify (dist/_redirects and dist/_headers), cloudflare (dist/_headers and dist/_redirects; the
// proxy is functions/api/[[path]].js), vercel (.vercel/output, Build Output API v3).
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(ROOT, "dist");

// Same headers the MDOS server sends (backend/mdos/main.py); a test keeps the two in step.
export const SECURITY_HEADERS = {
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; " +
    "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Resource-Policy": "same-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  "Strict-Transport-Security": "max-age=31536000",
};

/** The backend origin from MDOS_BACKEND_URL: https only, no credentials, path, query or fragment. */
export function backendOrigin(value) {
  let url;
  try {
    url = new URL(value ?? "");
  } catch {
    throw new Error("Set MDOS_BACKEND_URL to the backend address, for example https://your-space.hf.space");
  }
  if (url.protocol !== "https:") throw new Error("MDOS_BACKEND_URL must start with https://");
  if (url.username || url.password || url.search || url.hash || (url.pathname !== "/" && url.pathname !== "")) {
    throw new Error("MDOS_BACKEND_URL must be only the origin, for example https://your-space.hf.space");
  }
  return url.origin;
}

function headersFile() {
  const lines = Object.entries(SECURITY_HEADERS).map(([k, v]) => `  ${k}: ${v}`);
  return ["/*", ...lines, ""].join("\n");
}

function netlify(origin) {
  writeFileSync(join(DIST, "_headers"), headersFile());
  writeFileSync(join(DIST, "_redirects"), `/api/*  ${origin}/api/:splat  200!\n/*  /index.html  200\n`);
}

function cloudflare() {
  // The /api proxy is the Pages Function in functions/api/[[path]].js; it reads MDOS_BACKEND_URL at runtime.
  writeFileSync(join(DIST, "_headers"), headersFile());
  writeFileSync(join(DIST, "_redirects"), "/*  /index.html  200\n");
}

function vercel(origin) {
  const out = join(ROOT, ".vercel", "output");
  rmSync(out, { recursive: true, force: true });
  mkdirSync(join(out, "static"), { recursive: true });
  cpSync(DIST, join(out, "static"), { recursive: true });
  const config = {
    version: 3,
    routes: [
      { src: "/(.*)", headers: SECURITY_HEADERS, continue: true },
      { src: "/api/(.*)", dest: `${origin}/api/$1` },
      { handle: "filesystem" },
      { src: "/(.*)", dest: "/index.html" },
    ],
  };
  writeFileSync(join(out, "config.json"), JSON.stringify(config, null, 2));
}

function main() {
  const host = process.argv[2];
  if (!existsSync(join(DIST, "index.html"))) throw new Error("Build first: npm run build:dist");
  if (host === "cloudflare") {
    cloudflare();
  } else if (host === "netlify") {
    netlify(backendOrigin(process.env.MDOS_BACKEND_URL));
  } else if (host === "vercel") {
    vercel(backendOrigin(process.env.MDOS_BACKEND_URL));
  } else {
    throw new Error("Usage: node scripts/static-host.mjs netlify|cloudflare|vercel");
  }
  console.log(`Prepared dist for ${host}.`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
