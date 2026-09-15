import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["tests/unit/setup.ts"],
  },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  css: { postcss: { plugins: [] } },
});
