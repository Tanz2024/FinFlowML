import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const password = "Acceptance-password-123!";
const alpha = "alpha.acceptance.test";
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");

async function login(page: Page, role: string, host = alpha) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(`${role}@${host}`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/);
}

async function api(request: APIRequestContext, path: string, init?: Parameters<APIRequestContext["fetch"]>[1]) {
  const response = await request.fetch(`/api${path}`, init);
  const body = await response.json().catch(() => ({}));
  return { response, body };
}

async function waitForJob(request: APIRequestContext, jobId: string) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const result = await api(request, `/jobs/${jobId}`);
    if (["completed", "retryable_failed", "terminal_failed"].includes(result.body.state)) return result;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("extraction job did not finish within 15 seconds");
}

async function uploadReceipt(request: APIRequestContext, name: string, key: string) {
  const response = await request.post("/api/predict", {
    headers: { "Idempotency-Key": key },
    multipart: { receipt: { name, mimeType: "image/png", buffer: png } },
  });
  const body = await response.json().catch(() => ({}));
  return { response, body };
}

test("receipt extraction, review, correction, approval and protected image", async ({ page }) => {
  await login(page, "admin");
  const request = page.request;
  const filename = `acceptance-${Date.now()}.png`;
  const upload = await uploadReceipt(request, filename, `acceptance-${Date.now()}`);
  expect(upload.response.status()).toBe(202);
  expect(upload.body.mock).toBe(true);
  const completed = await waitForJob(request, upload.body.job_id);
  expect(completed.body.state).toBe("completed");

  const review = await api(request, `/receipts/${upload.body.receipt_id}/review`);
  expect(review.response.ok()).toBeTruthy();
  expect(review.body.fields.company.original_model_value).toBe("Mock Cafe");
  expect(review.body.fields.receipt_date.effective_value).toBe("2025-01-15");
  expect(review.body.fields.total.effective_value).toBe("12.50");

  const image = await api(request, `/receipts/${upload.body.receipt_id}/image`);
  expect(image.response.status()).toBe(200);
  expect(image.response.headers()["content-type"]).toContain("image/png");

  const correction = await api(request, `/receipts/${upload.body.receipt_id}/corrections`, {
    method: "PATCH",
    data: { corrections: { company: "Approved Demo Cafe" } },
  });
  expect(correction.response.ok()).toBeTruthy();
  const correctedReview = await api(request, `/receipts/${upload.body.receipt_id}/review`);
  expect(correctedReview.body.fields.company.status).toBe("corrected");
  expect(correctedReview.body.fields.company.original_model_value).toBe("Mock Cafe");
  expect(correctedReview.body.fields.company.effective_value).toBe("Approved Demo Cafe");

  const approved = await api(request, `/receipts/${upload.body.receipt_id}/approve`, { method: "POST" });
  expect(approved.response.status()).toBe(200);
  const repeated = await api(request, `/receipts/${upload.body.receipt_id}/approve`, { method: "POST" });
  expect(repeated.response.status()).toBe(200);
  expect(repeated.body.id).toBe(approved.body.id);
  const expenses = await api(request, "/expenses?search=Approved%20Demo%20Cafe");
  expect(expenses.response.ok()).toBeTruthy();
  expect(expenses.body.filter((item: { receipt_id: string }) => item.receipt_id === upload.body.receipt_id)).toHaveLength(1);
});

test("rejection, accounting workflows, currency summaries, roles and tenant isolation", async ({ page }) => {
  await login(page, "admin");
  const request = page.request;
  const upload = await uploadReceipt(request, "reject.png", `reject-${Date.now()}`);
  await waitForJob(request, upload.body.job_id);
  const rejected = await api(request, `/receipts/${upload.body.receipt_id}/reject`, { method: "POST" });
  expect(rejected.response.status()).toBe(200);
  const rejectedExpenses = await api(request, `/expenses?search=Mock%20Cafe`);
  expect(rejectedExpenses.body.some((item: { receipt_id: string }) => item.receipt_id === upload.body.receipt_id)).toBeFalsy();

  const suffix = Date.now();
  const customer = await api(request, "/customers", { method: "POST", data: { name: `Acceptance Customer ${suffix}` } });
  expect(customer.response.status()).toBe(201);
  const invoice = await api(request, "/invoices", { method: "POST", data: {
    customer_id: customer.body.id, invoice_number: `ACC-${suffix}`, invoice_date: "2025-01-01", due_date: "2025-02-01",
    subtotal: "100.00", tax: "0.00", total: "100.00", currency: "USD", items: [],
  } });
  expect(invoice.response.status()).toBe(201);
  const payment = await api(request, "/payments", { method: "POST", data: { invoice_id: invoice.body.id, payment_date: "2025-01-15", amount_paid: "40.00" } });
  expect(payment.response.status()).toBe(201);
  const overpayment = await api(request, "/payments", { method: "POST", data: { invoice_id: invoice.body.id, payment_date: "2025-01-16", amount_paid: "61.00" } });
  expect(overpayment.response.status()).toBe(422);

  const summary = await api(request, "/expenses/summary");
  expect(summary.response.ok()).toBeTruthy();
  expect(summary.body.currency_totals).toBeTruthy();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("button", { name: "Close navigation" })).toBeVisible();

  await page.goto("/login");
  await page.getByLabel("Email").fill(`viewer@${alpha}`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/);
  const viewerCustomer = await api(page.request, "/customers", { method: "POST", data: { name: `Forbidden ${suffix}` } });
  expect(viewerCustomer.response.status()).toBe(403);

  await page.goto("/login");
  await page.getByLabel("Email").fill(`admin@beta.acceptance.test`);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/);
  const crossTenant = await api(page.request, `/receipts/${upload.body.receipt_id}/review`);
  expect(crossTenant.response.status()).toBe(404);
});
