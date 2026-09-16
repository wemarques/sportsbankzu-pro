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
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.001, animations: "disabled" },
  },
  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: /visual\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      testIgnore: /visual\.spec\.ts/,
      use: { ...devices["iPhone 14"] },
    },
    {
      name: "visual-mobile",
      testMatch: /visual\.spec\.ts/,
      use: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, contextOptions: { reducedMotion: "reduce" } },
    },
    {
      name: "visual-desktop",
      testMatch: /visual\.spec\.ts/,
      use: { viewport: { width: 1440, height: 900 }, contextOptions: { reducedMotion: "reduce" } },
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
