/* How the API client reaches the server. The normal build talks to the MDOS server over HTTP; the live demo build
   swaps this module for src/demo/transport.ts, which runs the same server inside the browser (vite.config.ts). */

export const send: typeof fetch = (input, init) => fetch(input, init);

/** Open an HTML export in a new tab. The server sends it sandboxed (no scripts); the tab cannot reach this page. */
export async function openInNewTab(url: string): Promise<void> {
  window.open(url, "_blank", "noopener,noreferrer");
}

/** Present only in the live demo build (src/demo/transport.ts). */
export const demo: { reset: () => Promise<void> } | null = null;
