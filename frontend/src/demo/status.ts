/* The loading panel shown while the demo engine starts. Plain DOM, so it can appear before React draws. */

import type { EngineStatus } from "./protocol";

let panel: HTMLDivElement | null = null;

export function showStatus(status: EngineStatus): void {
  if (status.stage === "ready") {
    panel?.remove();
    panel = null;
    return;
  }
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "demo-boot";
    panel.setAttribute("role", "status");
    panel.setAttribute("aria-live", "polite");
    panel.innerHTML = `
      <div class="demo-boot-card">
        <h1>Starting the MDOS demo</h1>
        <p class="demo-boot-lead">The full app runs inside this browser. Nothing you enter leaves your device.</p>
        <div class="demo-boot-bar" aria-hidden="true"><span></span></div>
        <p class="demo-boot-detail"></p>
        <p class="demo-boot-note">The first visit downloads about 55 MB; later visits start faster.</p>
      </div>`;
    document.body.appendChild(panel);
  }
  const detail = panel.querySelector<HTMLParagraphElement>(".demo-boot-detail")!;
  const bar = panel.querySelector<HTMLSpanElement>(".demo-boot-bar span")!;
  detail.textContent = status.detail;
  bar.style.width = `${Math.round((status.progress ?? 0) * 100)}%`;
  if (status.stage === "failed") {
    panel.querySelector("h1")!.textContent = "The demo could not start";
    panel.classList.add("failed");
    const lead = panel.querySelector<HTMLParagraphElement>(".demo-boot-lead")!;
    lead.textContent = "This browser could not run the demo engine. Try a current version of Chrome, Edge, Firefox or Safari, or download the desktop app.";
  }
}
