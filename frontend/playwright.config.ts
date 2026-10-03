import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end smoke tests run against the real stack (no mocks): the Next.js app on
 * E2E_BASE_URL (default http://localhost:3000) and the StopLoss backend it proxies to.
 * Requires a Firebase email/password test account: E2E_EMAIL and E2E_PASSWORD.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 240_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-360", use: { ...devices["Pixel 5"], viewport: { width: 360, height: 780 } } },
  ],
});
