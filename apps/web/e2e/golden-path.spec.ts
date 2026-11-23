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

  // Layout rating (ARCH-155): admin rates, averages appear.
  await page.getByLabel("Usability").selectOption("4");
  await page.getByLabel("Comment").fill("Good light, tight kitchen");
  await page.getByRole("button", { name: "Save rating" }).click();
  await expect(page.getByTestId("rating-averages")).toContainText("4.0");

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

test("units switch between metres, feet, cm and mm", async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "set E2E_EMAIL and E2E_PASSWORD");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByLabel("Project name").fill(`E2E feet ${Date.now()}`);
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("link", { name: /E2E feet/ }).first().click();

  // Brief typed in feet is sent in metres and read back in feet.
  await page.getByTestId("units").selectOption("ft");
  await page.getByLabel("Plot width (ft)").fill("40");
  await page.getByLabel("Plot depth (ft)").fill("50");
  await page.getByRole("button", { name: "Generate options" }).click();
  await expect(page.getByText("plot 40.00 ft × 50.00 ft")).toBeVisible();
  await expect(page.getByTestId("option-card").first()).toContainText("ft² built-up");

  await page.getByTestId("option-card").first().click();
  await expect(page.getByText("Size (ft)", { exact: true })).toBeVisible();
  await expect(page.getByAltText("Plan of floor 0")).toHaveAttribute("src", /units=ft/);

  // Millimetres: lengths in mm, areas stay in m²; the choice survives a reload.
  await page.getByTestId("units").selectOption("mm");
  await expect(page.getByText("Size (mm)", { exact: true })).toBeVisible();
  await expect(page.getByText("Area (m²)", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("units")).toHaveValue("mm");
  await page.getByTestId("units").selectOption("m");
});

test("interior studio: theme, swap, decor, plants, finishes, save", async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "set E2E_EMAIL and E2E_PASSWORD");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByLabel("Project name").fill(`E2E interior ${Date.now()}`);
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("link", { name: /E2E interior/ }).first().click();
  await page.getByRole("button", { name: "Generate options" }).click();
  await page.getByTestId("option-card").first().click();
  await page.getByTestId("interior-link").click();

  // Suggested interior: living room is furnished and shown in plan and 3D.
  await expect(page.getByRole("heading", { name: "Interior studio" })).toBeVisible();
  const editor = page.getByTestId("room-editor");
  await expect(editor.locator('[data-item^="sofa"]')).toHaveCount(1);
  await expect(page.getByTestId("room-3d").locator("canvas")).toBeVisible();

  // Traditional theme furnishes the house with a pooja unit and teak furniture.
  page.once("dialog", (d) => d.accept());
  await page.getByLabel("Design theme").selectOption("traditional");
  await page.getByRole("button", { name: "Furnish whole house" }).click();
  await expect(editor.locator('[data-item="pooja_unit"]')).toHaveCount(1);

  // Swap the sofa and recolour it.
  await editor.locator('[data-item^="sofa"]').click();
  await page.getByLabel("Swap for").selectOption("sofa_leather");
  await expect(editor.locator('[data-item="sofa_leather"]')).toHaveCount(1);

  // Add a Buddha statue and an indoor plant from the catalogue.
  await page.getByRole("tab", { name: "Decor" }).click();
  await page.getByLabel("Search catalogue").fill("Buddha");
  await page.getByRole("button", { name: "Add Buddha statue, seated, 90 cm" }).click();
  await expect(editor.locator('[data-item="buddha_floor"]')).toHaveCount(1);
  await page.getByRole("tab", { name: "Plants" }).click();
  await page.getByLabel("Search catalogue").fill("");
  await page.getByRole("button", { name: "Add Monstera in planter" }).click();
  await expect(editor.locator('[data-item="plant_monstera"]')).toHaveCount(1);

  // Drag the plant into a corner with the mouse.
  const plant = editor.locator('[data-item="plant_monstera"]').last();
  const b = (await plant.boundingBox())!;
  const e = (await editor.boundingBox())!;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(e.x + e.width - 60, e.y + 60, { steps: 8 });
  await page.mouse.up();

  // Exposed brick walls and a herringbone floor.
  await page.getByRole("radio", { name: "Exposed brick" }).click();
  await page.getByRole("radio", { name: "Herringbone oak" }).click();
  await expect(page.getByRole("radio", { name: "Exposed brick" })).toHaveAttribute("aria-checked", "true");

  await expect(page.getByTestId("interior-total")).toContainText("₹");
  await page.getByTestId("save-interior").click();
  await expect(page.getByText(/Saved \(revision 1\)/)).toBeVisible();

  await page.reload();
  await expect(editor.locator('[data-item="buddha_floor"]')).toHaveCount(1);
  await expect(editor.locator('[data-item="sofa_leather"]')).toHaveCount(1);
  await expect(page.getByRole("radio", { name: "Herringbone oak" })).toHaveAttribute("aria-checked", "true");
});
