import { expect, test } from "@playwright/test";

// v0 golden path (ARCH-99): sign in, create project, submit brief, open an option,
// see plan, 3D view, checks, estimate, and download the IFC model.
test("brief to checked design with estimate and IFC", async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "set E2E_EMAIL and E2E_PASSWORD (make e2e does this)");

  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/projects$/);

  const name = `E2E house ${Date.now()}`;
  await page.getByLabel("Project name").fill(name);
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("link", { name: new RegExp(name) }).click();

  await page.getByRole("button", { name: "Generate options" }).click();
  const cards = page.getByTestId("option-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).toContainText("All checks pass");
  await cards.first().click();

  await expect(page.getByTestId("check-summary")).toContainText("All hard-rule checks pass");
  await expect(page.getByTestId("estimate-total")).toContainText("₹");
  const plan = page.getByAltText("Plan of floor 0");
  await expect(plan).toBeVisible();
  expect(await plan.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
  await expect(page.locator("canvas")).toBeVisible();
  // 3D floor toggle (ARCH-161): ground floor is shown first; whole house is one click away.
  const toggle = page.getByTestId("floor3d-toggle");
  await expect(toggle.getByRole("button", { name: "Ground" })).toBeVisible();
  await toggle.getByRole("button", { name: "Whole house" }).click();
  await expect(page.locator("canvas")).toBeVisible();

  // Actual cost (ARCH-154): off by default, admin turns it on, a recorded cost shows its estimate error.
  const optionUrl = page.url();
  await expect(page.getByText("Recording actual costs is off")).toBeVisible();
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByTestId("opt-in").check();
  await expect(page.getByTestId("opt-in")).toBeChecked();
  await page.goto(optionUrl);
  await page.getByLabel(/Actual total/).fill("1200000");
  await page.getByRole("button", { name: "Record" }).click();
  await expect(page.getByTestId("actual-costs")).toContainText("%");

  // Printable report (ARCH-87): same figures as the option page, with sources and limits.
  await page.getByTestId("report-link").click();
  await expect(page.getByTestId("report-total")).toContainText("₹");
  await expect(page.getByText("not for construction")).toBeVisible();
  await page.goBack();

  const download = page.waitForEvent("download");
  await page.getByTestId("download-ifc").click();
  expect((await download).suggestedFilename()).toMatch(/\.ifc$/);
});

test("invalid brief shows a readable error", async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "set E2E_EMAIL and E2E_PASSWORD");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByLabel("Project name").fill(`E2E tiny ${Date.now()}`);
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("link", { name: /E2E tiny/ }).first().click();
  await page.getByLabel("Plot width (m)").fill("5");
  await page.getByLabel("Plot depth (m)").fill("6");
  await page.getByRole("button", { name: "Generate options" }).click();
  // Next.js adds its own role=alert route announcer, so match our message by text.
  await expect(page.getByRole("alert").filter({ hasText: /plot allows|buildable/ })).toBeVisible();
  await expect(page.getByText("Value error")).toHaveCount(0);
});
