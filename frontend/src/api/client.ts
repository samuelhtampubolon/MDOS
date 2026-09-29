/* Thin fetch wrapper: bearer token, JSON, typed errors and file downloads. */

const TOKEN_KEY = "mdos.token";

let token: string | null = null;

function readStored(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(value: string | null, persist = false): void {
  token = value;
  try {
    if (value && persist) window.localStorage.setItem(TOKEN_KEY, value);
    if (!value) window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: keep the token in memory only */
  }
}

export function getToken(): string | null {
  if (!token) token = readStored();
  return token;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const BASE = "/api/v1";

async function request<T>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (isForm) {
      payload = body as FormData;
    } else {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const err = (data as { error?: { code: string; message: string; details?: Record<string, unknown> }; detail?: unknown }) || {};
    if (err.error) throw new ApiError(res.status, err.error.code, err.error.message, err.error.details || {});
    const detail = Array.isArray(err.detail) ? (err.detail[0] as { msg?: string })?.msg : String(err.detail ?? res.statusText);
    throw new ApiError(res.status, "http_error", detail || "Request failed");
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  del: <T = void>(path: string) => request<T>("DELETE", path),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, form, true),
};

/** Download a file from an authenticated endpoint. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const t = getToken();
  const res = await fetch(`${BASE}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "download_failed", "Download failed");
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = match ? match[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** Open an authenticated HTML export in a new tab. */
export async function openHtml(path: string): Promise<void> {
  const t = getToken();
  const win = window.open("", "_blank");
  const res = await fetch(`${BASE}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
  const html = await res.text();
  if (win) {
    win.document.open();
    win.document.write(html);
    win.document.close();
  }
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
