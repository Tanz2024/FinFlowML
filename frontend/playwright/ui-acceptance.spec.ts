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
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Approve expense" }).click();
  await expect(page.getByText("Approved and expense created")).toBeVisible();
});

test("receipt review UI rejects a receipt without creating an expense", async ({ page }) => {
  await login(page);
  await page.goto("/scan");
  const filename = `ui-reject-${Date.now()}.png`;
  await page.locator('input[type="file"]').setInputFiles({ name: filename, mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "Start extraction" }).click();
  await expect(page).toHaveURL(/\/review\//, { timeout: 20_000 });
  const receiptId = page.url().split("/").pop() as string;
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByText("Receipt rejected")).toBeVisible();
  const expenses = await page.request.get("/api/expenses?search=Mock%20Cafe");
  const rows = await expenses.json();
  expect(rows.some((item: { receipt_id: string }) => item.receipt_id === receiptId)).toBeFalsy();
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

test("scanner resumes an existing job without uploading it again", async ({ page }) => {
  await login(page, "admin");
  let predictCalls = 0;
  let jobReads = 0;
  await page.route("**/api/predict", async (route) => {
    predictCalls += 1;
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ job_id: "job-resume", receipt_id: "receipt-resume", mock: true }) });
  });
  await page.route("**/api/jobs/job-resume", async (route) => {
    jobReads += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: jobReads < 2 ? "processing" : "completed" }) });
  });
  await page.route("**/api/receipts/receipt-resume/review", async (route) => {
    const fields = Object.fromEntries(["company", "receipt_date", "address", "total", "currency"].map((field) => [field, { original_model_value: null, normalized_value: null, reviewer_corrected_value: null, effective_value: null, status: "missing", errors: [] }]));
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ receipt_id: "receipt-resume", status: "needs_review", fields, validation_errors: [] }) });
  });
  await page.clock.install();
  await page.goto("/scan");
  await page.getByLabel(/Drop a receipt here/).setInputFiles({ name: "resume.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "Start extraction" }).click();
  await expect.poll(() => jobReads).toBeGreaterThan(0);
  await page.clock.fastForward(1_100);
  await expect(page).toHaveURL(/review\/receipt-resume/);
  expect(predictCalls).toBe(1);
  expect(jobReads).toBeGreaterThanOrEqual(2);
});
