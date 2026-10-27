/* The live demo, driven like a visitor: the whole app runs in the browser (Pyodide), nothing leaves the page. One
   page is shared by the tests because the demo's server lives in that page's worker. */

import { expect, test, type Page } from "@playwright/test";

test.describe.configure({ mode: "serial" });

let page: Page;
let pid = "";
const errors: string[] = [];
const offsite: string[] = [];

test.beforeAll(async ({ browser, baseURL }) => {
  page = await browser.newPage();
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  page.on("response", (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
  page.on("request", (r) => {
    const url = r.url();
    if (!url.startsWith(baseURL!) && !url.startsWith("blob:") && !url.startsWith("data:")) offsite.push(url);
  });
});

test.afterAll(async () => {
  await page.close();
});

async function open(route: string): Promise<void> {
  await page.goto(`./#/${route}`);
}

test("the engine starts and the app opens without a server", async () => {
  await page.goto("./");
  await expect(page.getByRole("heading", { name: "Starting the MDOS demo" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /From business question to defensible marketing evidence/ })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByRole("complementary", { name: "About this demo" })).toContainText("Live demo");
  await expect(page.getByText("Live demo: this browser only")).toBeVisible();
});

test("load the Lake Toba demo; the agents run in the browser", async () => {
  await page.getByRole("button", { name: /Load the Lake Toba demo/ }).click();
  await page.waitForURL(/#\/p\/[^/]+/, { timeout: 300_000 });
  pid = /#\/p\/([^/]+)/.exec(page.url())![1];
  await expect(page.getByText(/Next step:/)).toBeVisible();
  await expect(page.getByText("Evidence records", { exact: true })).toBeVisible();
});

test("every module renders", async () => {
  const routes: [string, RegExp][] = [
    ["research/dashboard", /Research workflow/], ["research/plan", /Hypothesis canvas/], ["research/questionnaire", /Export/],
    ["research/data", /Data quality/], ["research/analysis", /Run an analysis/], ["research/insights", /Quality gates/],
    ["research/report", /New report/], ["strategy", /Monthly profit by scenario/], ["journey", /Emotion along the journey/],
    ["data", /Data lineage/], ["agents", /The agent team/], ["reports", /Reports that cite their evidence/],
    ["experiments", /Test before you roll out/], ["approvals", /Approvals/], ["settings", /Audit log/],
  ];
  for (const [route, marker] of routes) {
    await open(`p/${pid}/${route}`);
    await expect(page.getByText(marker).first()).toBeVisible();
  }
});

test("a person approves an insight; causal wording is blocked without an experiment", async () => {
  await open(`p/${pid}/research/insights`);
  const card = page.locator("section.card", { has: page.getByRole("button", { name: "Approve" }) }).first();
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/I\d+ approved\./)).toBeVisible();
  await page.getByText("Write an insight").click();
  await page.getByLabel("Title").fill("Authenticity and intention");
  await page.getByLabel("Statement").fill("Perceived authenticity increases purchase intention.");
  await page.locator("form").getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Save draft insight" }).click();
  await expect(page.getByText("Causal wording needs experimental evidence")).toBeVisible();
});

test("simulate a pricing scenario", async () => {
  await open(`p/${pid}/strategy`);
  await page.getByLabel("Scenario name").fill("Demo launch at Rp 150.000");
  await page.getByLabel("New price").fill("150000");
  await page.getByRole("button", { name: "Simulate scenario" }).click();
  await expect(page.getByRole("tab", { name: "Demo launch at Rp 150.000" })).toBeVisible();
});

test("upload a CSV file and check its quality", async () => {
  await open(`p/${pid}/research/data`);
  await page.getByLabel("File").setInputFiles("../samples/lake_toba_reviews.csv");
  await page.getByLabel("Name (optional)").fill("Uploaded reviews");
  await page.getByLabel("What is it?").selectOption("reviews");
  await page.getByRole("button", { name: "Upload and check quality" }).click();
  await expect(page.getByText("Uploaded reviews").first()).toBeVisible();
});

test("the HTML report export opens with every script blocked", async () => {
  await open(`p/${pid}/research/report`);
  await page.getByRole("button", { name: "Generate" }).click();
  const popup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Printable HTML" }).click();
  const tab = await popup;
  await tab.waitForURL(/^blob:/);
  const policy = await tab.locator('meta[http-equiv="Content-Security-Policy"]').first().getAttribute("content");
  expect(policy).toContain("default-src 'none'");
  await tab.close();
});

test("on a phone, pages fit the screen", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["research", "strategy", "journey", "data", "settings"]) {
    await open(`p/${pid}/${route}`);
    await expect(page.locator("main")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${route} is wider than the screen`).toBeLessThanOrEqual(0);
  }
  await page.setViewportSize({ width: 1440, height: 950 });
});

test("projects survive a reload, and Reset demo clears them", async () => {
  await open(`p/${pid}/research`);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Lake Toba cultural experience (demo)" })).toBeVisible({ timeout: 300_000 });
  await open(`p/${pid}/strategy`);
  await expect(page.getByRole("tab", { name: "Demo launch at Rp 150.000" })).toBeVisible(); // made before the reload
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(page.getByRole("button", { name: /Load the Lake Toba demo/ })).toBeVisible({ timeout: 300_000 });
});

test("no errors and no requests to other sites", async () => {
  expect(errors).toEqual([]);
  expect(offsite).toEqual([]);
});
