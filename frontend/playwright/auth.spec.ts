import { test, expect } from "@playwright/test";

test("login, protected dashboard and logout", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@alpha.acceptance.test");
  await page.getByLabel("Password").fill("Acceptance-password-123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByRole("heading", { name: "Financial dashboard" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/login/);
});

test("failed login is visible", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@alpha.acceptance.test");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
});
