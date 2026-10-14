import { test, expect } from "@playwright/test";

const password = "Acceptance-password-123!";
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");

async function login(page: import("@playwright/test").Page, role = "admin") {
  await page.goto("/login");
  await page.getByLabel("Email").fill(`${role}@alpha.acceptance.test`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/);
}

test("scanner UI uploads, completes mock extraction and saves a review correction", async ({ page }) => {
  await login(page);
  await page.goto("/scan");
  await expect(page.getByRole("heading", { name: /Turn receipts/ })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({ name: `ui-${Date.now()}.png`, mimeType: "image/png", buffer: png });
  await expect(page.getByText(/ui-.*\.png/)).toBeVisible();
  await page.getByRole("button", { name: "Start extraction" }).click();
  await expect(page.getByText(/mock extraction/)).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/review\//, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "Review extraction" })).toBeVisible();
  const company = page.getByLabel("Company");
  await company.fill("UI Corrected Cafe");
  await expect(page.getByRole("button", { name: "Approve expense" })).toBeDisabled();
  await page.getByRole("button", { name: "Save corrections" }).click();
  await expect(page.getByText("Corrections saved")).toBeVisible();
  await expect(company).toHaveValue("UI Corrected Cafe");
});

test("financial forms create a customer, invoice and payment through the UI", async ({ page }) => {
  await login(page, "accountant");
  const suffix = Date.now();
  await page.goto("/customers");
  await page.getByPlaceholder("Customer name").fill(`UI Customer ${suffix}`);
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText(`UI Customer ${suffix}`)).toBeVisible();

  await page.goto("/invoices");
  await page.getByRole("combobox").first().selectOption({ label: `UI Customer ${suffix}` });
  await page.getByPlaceholder("Invoice number").fill(`UI-${suffix}`);
  await page.locator('input[type="date"]').nth(0).fill("2025-01-01");
  await page.locator('input[type="date"]').nth(1).fill("2025-02-01");
  await page.getByPlaceholder("Subtotal").fill("100.00");
  await page.getByPlaceholder("Tax").fill("5.00");
  await page.getByRole("button", { name: "Create invoice" }).click();
  await expect(page.getByText(`UI-${suffix}`)).toBeVisible();

  await page.goto("/payments");
  await page.getByRole("combobox").selectOption({ label: `UI-${suffix} · MYR 105.00` });
  await page.locator('input[type="date"]').fill("2025-01-15");
  await page.locator('input[type="number"]').fill("40.00");
  await page.getByRole("button", { name: "Record payment" }).click();
  await expect(page.getByText("Payment created")).toBeVisible();
  await page.locator('input[type="number"]').fill("70.00");
  await page.getByRole("button", { name: "Record payment" }).click();
  await expect(page.locator("p.text-red-700")).toContainText(/exceed|balance|payment/i);
});

test("dashboard keeps currency selection explicit and mobile navigation works", async ({ page }) => {
  await login(page);
  await expect(page.getByLabel("Chart currency")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("button", { name: "Close navigation" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Pending reviews" })).toBeVisible();
});
