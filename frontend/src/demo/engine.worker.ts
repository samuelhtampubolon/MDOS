/* The demo engine: loads Pyodide and the MDOS server from this site, then answers the page's API requests.
   Projects are kept in IndexedDB (Emscripten's IDBFS), so they survive a reload; "Reset demo" clears them. */

import type { DemoManifest, EngineReply, EngineRequest, EngineReset, EngineStatus } from "./protocol";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Pyodide = any;

const DATA_DIR = "/mdos-data";
const scope = self as unknown as { postMessage: (msg: unknown, transfer?: Transferable[]) => void; onmessage: unknown };

function status(stage: EngineStatus["stage"], detail: string, progress?: number): void {
  scope.postMessage({ kind: "status", stage, detail, progress } satisfies EngineStatus);
}

let py: Pyodide = null;
let handle: any = null;
let saving: Promise<void> = Promise.resolve();

function sync(populate: boolean): Promise<void> {
  return new Promise((resolve, reject) => py.FS.syncfs(populate, (err: unknown) => (err ? reject(err) : resolve())));
}

/** Save to IndexedDB after changes, one save at a time. */
function save(): Promise<void> {
  saving = saving.then(() => sync(false)).catch(() => undefined);
  return saving;
}

async function fetchBytes(url: URL): Promise<Uint8Array> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url.pathname} (${res.status}).`);
  return new Uint8Array(await res.arrayBuffer());
}

async function boot(root: URL): Promise<void> {
  status("loading", "Reading the demo manifest", 0.02);
  const manifest = (await (await fetch(new URL("demo-manifest.json", root))).json()) as DemoManifest;
  const indexURL = new URL(manifest.pyodide, root).href;

  status("loading", "Starting Python", 0.06);
  const { loadPyodide } = await import(/* @vite-ignore */ `${indexURL}pyodide.mjs`);
  py = await loadPyodide({ indexURL, stdout: () => undefined, stderr: () => undefined });

  let loaded = 0;
  const total = manifest.packages.length;
  await py.loadPackage(manifest.packages, {
    messageCallback: (msg: string) => {
      if (msg.startsWith("Loaded")) return;
      loaded = Math.min(loaded + 1, total);
      status("loading", "Loading the statistics libraries", 0.1 + 0.6 * (loaded / total));
    },
    errorCallback: () => undefined,
  });

  status("loading", "Installing MDOS", 0.75);
  py.FS.mkdirTree("/home/pyodide/wheels");
  for (const wheel of manifest.wheels) {
    py.FS.writeFile(`/home/pyodide/wheels/${wheel}`, await fetchBytes(new URL(`wheels/${wheel}`, root)));
  }
  py.FS.writeFile("/home/pyodide/mdos.zip", await fetchBytes(new URL(manifest.app, root)));
  await py.runPythonAsync(`
import glob, site, sys, zipfile
packages = site.getsitepackages()[0]
for wheel in glob.glob("/home/pyodide/wheels/*.whl"):
    zipfile.ZipFile(wheel).extractall(packages)
zipfile.ZipFile("/home/pyodide/mdos.zip").extractall("/home/pyodide/app")
sys.path.insert(0, "/home/pyodide/app")
`);

  status("loading", "Opening your saved demo projects", 0.85);
  py.FS.mkdirTree(DATA_DIR);
  py.FS.mount(py.FS.filesystems.IDBFS, {}, DATA_DIR);
  await sync(true);

  status("loading", "Starting the MDOS server", 0.9);
  await py.runPythonAsync(`
from mdos import browser
await browser.boot("${DATA_DIR}")

async def mdos_handle(method, path, query, headers, body):
    pairs = [[str(k), str(v)] for k, v in headers]
    return await browser.handle(method, path, query, pairs, body.to_bytes())

def mdos_reset():
    import os, shutil
    for name in os.listdir("${DATA_DIR}"):
        target = os.path.join("${DATA_DIR}", name)
        shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)
`);
  handle = py.globals.get("mdos_handle");
  await save();
  status("ready", "Ready", 1);
}

async function answer(req: EngineRequest): Promise<void> {
  let reply: EngineReply;
  try {
    const result = await handle(req.method, req.path, req.query, req.headers, new Uint8Array(req.body));
    const js = result.toJs({ dict_converter: Object.fromEntries });
    result.destroy();
    const body = (js.body as Uint8Array).slice().buffer;
    reply = { kind: "reply", id: req.id, status: js.status, headers: js.headers, body };
    if (req.method !== "GET" && req.method !== "HEAD") await save();
  } catch (err) {
    const text = JSON.stringify({ error: { code: "demo_engine", message: `The demo engine failed: ${String(err).slice(0, 300)}` } });
    reply = { kind: "reply", id: req.id, status: 500, headers: [["content-type", "application/json"]], body: new TextEncoder().encode(text).buffer };
  }
  scope.postMessage(reply, [reply.body]);
}

let booting: Promise<void> | null = null;

scope.onmessage = async (event: MessageEvent<{ kind: "init"; root: string } | EngineRequest | EngineReset>) => {
  const msg = event.data;
  if (msg.kind === "init") {
    booting = boot(new URL(msg.root)).catch((err) => status("failed", String(err?.message ?? err).slice(0, 300)));
    return;
  }
  await booting;
  if (msg.kind === "request") await answer(msg);
  else if (msg.kind === "reset") {
    py.globals.get("mdos_reset")();
    await save();
    scope.postMessage({ kind: "reply", id: msg.id, status: 204, headers: [], body: new ArrayBuffer(0) } satisfies EngineReply);
  }
};
