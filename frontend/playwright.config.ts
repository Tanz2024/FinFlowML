import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir: "./playwright", use: { baseURL: "http://127.0.0.1:3000", browserName: "chromium", headless: true, launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } }, timeout: 30_000 });
