import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir: "./playwright", reporter: "line", projects: [{ name: "chromium", use: { baseURL: "http://127.0.0.1:3000", browserName: "chromium", headless: true, trace: "retain-on-failure", screenshot: "only-on-failure", launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } } }], timeout: 30_000 });
