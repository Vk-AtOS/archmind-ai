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
