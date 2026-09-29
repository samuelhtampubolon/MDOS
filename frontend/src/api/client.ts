/* Thin fetch wrapper: cookie session, CSRF header, JSON, typed errors and file downloads.
   The session lives in an HttpOnly cookie that page scripts cannot read, so the app never stores a token. */

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
// The server rejects cookie-authenticated changes without this header; other sites cannot add it (CSRF defense).
const CSRF_HEADERS: Record<string, string> = { "X-Requested-With": "mdos" };

let unauthorizedHandler: (() => void) | null = null;

/** Called when the server says the session ended (expired, signed out elsewhere, or MDOS restarted). */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function request<T>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = { ...CSRF_HEADERS };
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (isForm) {
      payload = body as FormData;
    } else {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload, credentials: "same-origin" });
  if (res.status === 401 && !path.startsWith("/auth/")) unauthorizedHandler?.();
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
  del: <T = void>(path: string, body?: unknown) => request<T>("DELETE", path, body),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, form, true),
};

/** Download a file from an authenticated endpoint (the session cookie authenticates the request). */
export async function download(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { headers: CSRF_HEADERS, credentials: "same-origin" });
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

/** Open an HTML export in a new tab. The server sends it sandboxed (no scripts); the tab cannot reach this page. */
export function openHtml(path: string): void {
  window.open(`${BASE}${path}`, "_blank", "noopener,noreferrer");
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
