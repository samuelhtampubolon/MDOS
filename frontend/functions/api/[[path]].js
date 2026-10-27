// MDOS, Marketing Decision OS. Copyright © 2026 Samuel Hasudungan Tampubolon. Released under the MIT License.
//
// Cloudflare Pages Function: forwards /api/* to the MDOS backend named in the MDOS_BACKEND_URL environment
// variable, so the interface and the API share one site (the session cookie stays SameSite=Strict).
// It only ever calls that one https origin, keeps the original path under /api/, and never follows redirects.

export async function onRequest({ request, env }) {
  let backend;
  try {
    backend = new URL(env.MDOS_BACKEND_URL ?? "");
  } catch {
    return new Response("MDOS_BACKEND_URL is not set.", { status: 500 });
  }
  if (backend.protocol !== "https:") {
    return new Response("MDOS_BACKEND_URL must start with https://.", { status: 500 });
  }
  const incoming = new URL(request.url);
  if (!incoming.pathname.startsWith("/api/")) {
    return new Response("Not found.", { status: 404 });
  }
  const target = new URL(incoming.pathname + incoming.search, backend.origin);
  const init = { method: request.method, headers: request.headers, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }
  return fetch(target.toString(), init);
}
