import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: process.env.STAFF_MOBILE_BASE_URL || "http://127.0.0.1:3001",
    headless: true,
  },
});