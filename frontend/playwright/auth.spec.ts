import { test, expect } from "@playwright/test";

test("login, protected dashboard and logout", async ({ page, context }) => {
  await test.step("login succeeds", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@alpha.acceptance.test");
    await page.getByLabel("Password").fill("Acceptance-password-123!");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/dashboard/);
  });
  await test.step("dashboard is visible", async () => {
    await expect(page.getByRole("heading", { name: "Financial dashboard" })).toBeVisible();
  });
  const signOut = page.getByRole("button", { name: "Sign out" }).first();
  await test.step("logout request succeeds", async () => {
    await expect(signOut).toBeVisible();
    await expect(signOut).toBeEnabled();
    const response = await Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/auth/logout") && r.request().method() === "POST"), signOut.click()]);
    expect(response[0].status()).toBe(200);
  });
  await test.step("cookie and session are invalidated", async () => {
    expect((await context.cookies()).some((cookie) => cookie.name === "finflow_token" && cookie.value)).toBe(false);
    await expect(page).toHaveURL(/login/);
    expect((await page.request.get("/api/auth/me")).status()).toBe(401);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Financial dashboard" })).not.toBeVisible();
    await expect(page).toHaveURL(/login/);
  });
});

test("failed login is visible", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@alpha.acceptance.test");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
});

