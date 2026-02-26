import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "fs";
import { join } from "path";

const hasProductionBuild = existsSync(join(__dirname, ".next", "BUILD_ID"));
const useDevServer = !process.env.CI || !hasProductionBuild;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 14"] },
    },
  ],
  webServer: {
    command: useDevServer ? "npm run dev" : "npm run start",
    url: "http://localhost:3001",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { PORT: "3001" },
  },
});
