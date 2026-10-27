/* Live demo transport: the MDOS server runs inside this browser tab, in a Web Worker with Pyodide (Python compiled
   to WebAssembly), and every API call goes to it instead of the network. Nothing is sent anywhere; projects are
   kept in this browser's storage. The worker is engine.worker.ts; the server side is backend/mdos/browser.py. */

import type { EngineReply, EngineRequest, EngineStatus } from "./protocol";
import { showStatus } from "./status";
import "./demo.css";

let worker: Worker | null = null;
let ready: Promise<void> | null = null;
let nextId = 1;
const waiting = new Map<number, (reply: EngineReply) => void>();

function start(): Promise<void> {
  if (ready) return ready;
  ready = new Promise<void>((resolve, reject) => {
    worker = new Worker(new URL("./engine.worker.ts", import.meta.url), { type: "module", name: "mdos-engine" });
    worker.onmessage = (event: MessageEvent<EngineStatus | EngineReply>) => {
      const msg = event.data;
      if (msg.kind === "status") {
        showStatus(msg);
        if (msg.stage === "ready") resolve();
        if (msg.stage === "failed") reject(new Error(msg.detail));
      } else {
        waiting.get(msg.id)?.(msg);
        waiting.delete(msg.id);
      }
    };
    worker.postMessage({ kind: "init", root: new URL("./", window.location.href).href });
    worker.onerror = (event) => {
      showStatus({ kind: "status", stage: "failed", detail: event.message || "The demo engine stopped." });
      reject(new Error(event.message));
    };
  });
  return ready;
}

/** Ask the engine to answer one request, as the network would. */
export const send: typeof fetch = async (input, init) => {
  const request = new Request(input instanceof Request ? input : new URL(String(input), window.location.href), init);
  await start();
  const url = new URL(request.url);
  const body = request.method === "GET" || request.method === "HEAD" ? new ArrayBuffer(0) : await request.arrayBuffer();
  const id = nextId++;
  const message: EngineRequest = {
    kind: "request", id, method: request.method, path: url.pathname, query: url.search.slice(1),
    headers: [...request.headers.entries()], body,
  };
  const reply = await new Promise<EngineReply>((resolve) => {
    waiting.set(id, resolve);
    worker!.postMessage(message, [body]);
  });
  const empty = reply.status === 204 || reply.status === 304;
  return new Response(empty ? null : reply.body, { status: reply.status, headers: reply.headers });
};

/** Open an HTML export in a new tab. The page is shown from a blob with a policy that blocks every script, the
   protection the server's sandbox header gives it outside the demo. */
export async function openInNewTab(url: string): Promise<void> {
  const tab = window.open("about:blank", "_blank"); // opened during the click, so pop-up blockers allow it
  if (tab) tab.opener = null;
  const res = await send(url);
  const html = await res.text();
  const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">`;
  const page = html.replace(/<head[^>]*>/i, (head) => head + policy);
  const blob = new Blob([page.includes(policy) ? page : policy + page], { type: "text/html" });
  const blobUrl = URL.createObjectURL(blob);
  if (tab) tab.location.href = blobUrl;
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

/** Delete every demo project from this browser and start again. */
export async function resetDemo(): Promise<void> {
  await start();
  await new Promise<void>((resolve) => {
    const id = nextId++;
    waiting.set(id, () => resolve());
    worker!.postMessage({ kind: "reset", id });
  });
  window.location.hash = "";
  window.location.reload();
}

/** Present only in the demo build: the app shows a demo bar with these actions. */
export const demo = { reset: resetDemo };

void start(); // begin loading Python while the interface draws
