/* The Lake Toba demo, driven like a user: research to strategy to journey to experiment and back to evidence. */

import { expect, test, type Page } from "@playwright/test";

let pid = "";

async function token(page: Page): Promise<string> {
  const res = await page.request.post("/api/v1/auth/local-session");
  return (await res.json()).access_token as string;
}

function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  return errors;
}

test.describe.serial("closed loop on the demo project", () => {
  test("load the demo and wait for the agents", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /From business question to defensible marketing evidence/ })).toBeVisible();
    await page.getByRole("button", { name: /Load the Lake Toba demo/ }).click();
    await page.waitForURL(/\/p\/[^/]+\/research/);
    pid = new URL(page.url()).pathname.split("/")[2];
    const auth = { Authorization: `Bearer ${await token(page)}` };
    await expect.poll(async () => (await (await page.request.get(`/api/v1/projects/${pid}`, { headers: auth })).json()).brief?.demo_status,
      { timeout: 240_000, intervals: [1000] }).toBe("ready");
    await page.reload();
    await expect(page.getByText(/Next step:/)).toBeVisible();
    await expect(page.getByText("Evidence records", { exact: true })).toBeVisible();
  });

  test("every module renders without errors", async ({ page }, testInfo) => {
    const errors = watchErrors(page);
    const routes: [string, RegExp][] = [
      ["research/dashboard", /Research workflow/], ["research/plan", /Hypothesis canvas/], ["research/questionnaire", /Export/],
      ["research/data", /Data quality/], ["research/analysis", /Run an analysis/], ["research/insights", /Quality gates/],
      ["research/report", /New report/], ["strategy", /Monthly profit by scenario/], ["journey", /Emotion along the journey/],
      ["data", /Data lineage/], ["agents", /The agent team/], ["reports", /Reports that cite their evidence/],
      ["experiments", /Test before you roll out/], ["approvals", /Approvals/], ["settings", /Audit log/],
    ];
    for (const [route, marker] of routes) {
      await page.goto(`/p/${pid}/${route}`);
      await expect(page.getByText(marker).first()).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath(`${route.replace("/", "-")}.png`), fullPage: true });
    }
    expect(errors).toEqual([]);
  });

  test("a person approves an insight; causal wording is blocked without an experiment", async ({ page }) => {
    await page.goto(`/p/${pid}/research/insights`);
    const card = page.locator("section.card", { has: page.getByRole("button", { name: "Approve" }) }).first();
    await card.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText(/I\d+ approved\./)).toBeVisible();

    await page.getByText("Write an insight").click();
    await page.getByLabel("Title").fill("Authenticity and intention");
    await page.getByLabel("Statement").fill("Perceived authenticity increases purchase intention.");
    await page.locator("form").getByRole("checkbox").first().check();
    await page.getByRole("button", { name: "Save draft insight" }).click();
    await expect(page.getByText("Causal wording needs experimental evidence")).toBeVisible();
    await page.getByRole("button", { name: "Use this wording" }).click();
    await expect(page.getByLabel("Statement")).toHaveValue(/is associated with higher/);
    await page.getByRole("button", { name: "Save draft insight" }).click();
    await expect(page.getByText("Insight saved as a draft.")).toBeVisible();
  });

  test("add a hypothesis and size a sample on the research plan", async ({ page }) => {
    await page.goto(`/p/${pid}/research/plan`);
    await page.getByText("Add a hypothesis").click();
    await page.getByLabel("Statement").fill("Guide storytelling quality is positively associated with satisfaction.");
    await page.getByLabel("Independent variable", { exact: true }).fill("storytelling");
    await page.getByLabel("Dependent variable", { exact: true }).fill("satisfaction");
    await page.getByRole("button", { name: "Add hypothesis" }).click();
    await expect(page.getByText("Hypothesis added.")).toBeVisible();
    await expect(page.getByText("Guide storytelling quality is positively associated with satisfaction.")).toBeVisible();
    await page.getByRole("button", { name: "Calculate" }).click();
    await expect(page.getByText("n = 385")).toBeVisible(); // 50% share, ±5 points, 95% confidence
  });

  test("add a journey touchpoint", async ({ page }) => {
    await page.goto(`/p/${pid}/journey`);
    await page.getByRole("tab", { name: "Stages and settings" }).click();
    await page.getByLabel("Touchpoint name").fill("Hotel front desk");
    await page.getByLabel("Channel").fill("In person");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByRole("cell", { name: "Hotel front desk", exact: true })).toBeVisible();
  });

  test("simulate a pricing scenario", async ({ page }) => {
    await page.goto(`/p/${pid}/strategy`);
    await page.getByLabel("Scenario name").fill("E2E launch at Rp 150.000");
    await page.getByLabel("New price").fill("150000");
    await page.getByRole("button", { name: "Simulate scenario" }).click();
    await expect(page.getByRole("tab", { name: "E2E launch at Rp 150.000" })).toBeVisible();
    await expect(page.getByText("Profit bridge from the baseline")).toBeVisible();
  });

  test("intervention to A/B test to experimental evidence", async ({ page }) => {
    await page.goto(`/p/${pid}/journey`);
    await page.getByRole("tab", { name: /^Interventions/ }).click();
    await page.getByRole("button", { name: "Design an A/B test" }).first().click();
    await page.waitForURL(/\/experiments$/);
    await page.getByRole("button", { name: "Approve launch" }).first().click();
    await expect(page.getByText("Enter results").first()).toBeVisible();
    await page.getByLabel("Control visitors").first().fill("5000");
    await page.getByLabel("Control conversions").first().fill("3000");
    await page.getByLabel("Treatment visitors").first().fill("5000");
    await page.getByLabel("Treatment conversions").first().fill("3250");
    await page.getByRole("button", { name: "Analyze results" }).first().click();
    await expect(page.getByText(/Saved as evidence E\d+/).first()).toBeVisible();
  });

  test("approvals page decides pending requests", async ({ page }) => {
    await page.goto(`/p/${pid}/approvals`);
    await expect(page.getByRole("tab", { name: /Waiting \(\d+\)/ })).toBeVisible();
    await page.getByRole("button", { name: "Approve" }).first().click();
    await expect(page.getByText("Approved.")).toBeVisible();
  });
});

test.describe("dark theme", () => {
  test.use({ colorScheme: "dark" });
  test("home and strategy render in dark mode", async ({ page }, testInfo) => {
    const errors = watchErrors(page);
    await page.goto("/");
    await page.screenshot({ path: testInfo.outputPath("home-dark.png"), fullPage: true });
    if (pid) {
      await page.goto(`/p/${pid}/strategy`);
      await expect(page.getByText("Monthly profit by scenario")).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath("strategy-dark.png"), fullPage: true });
    }
    expect(errors).toEqual([]);
  });
});
