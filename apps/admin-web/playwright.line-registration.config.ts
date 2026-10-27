import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["line-registration-ui.spec.ts", "worker-line-inbox-ui.spec.ts"],
  workers: 1,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:4317", viewport: { width: 390, height: 844 }, browserName: "chromium", channel: process.env.PLAYWRIGHT_CHANNEL },
  webServer: {
    command: "node e2e/line-registration-preview.mjs",
    url: "http://127.0.0.1:4317",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
