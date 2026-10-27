/* Messages between the page and the demo engine worker. */

export interface EngineRequest {
  kind: "request";
  id: number;
  method: string;
  path: string;
  query: string;
  headers: [string, string][];
  body: ArrayBuffer;
}

export interface EngineReset {
  kind: "reset";
  id: number;
}

export interface EngineReply {
  kind: "reply";
  id: number;
  status: number;
  headers: [string, string][];
  body: ArrayBuffer;
}

export interface EngineStatus {
  kind: "status";
  stage: "loading" | "ready" | "failed";
  detail: string;
  /** 0 to 1 while loading. */
  progress?: number;
}

/** What the build puts next to the demo (scripts/build_demo.py): Pyodide packages, extra wheels and the app. */
export interface DemoManifest {
  pyodide: string;
  packages: string[];
  wheels: string[];
  app: string;
}
