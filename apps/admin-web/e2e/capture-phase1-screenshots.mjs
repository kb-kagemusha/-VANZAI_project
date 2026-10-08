import { chromium } from "playwright";
import { fileURLToPath } from "node:url";

const baseUrl = process.env.ADMIN_WEB_BASE_URL || "http://127.0.0.1:3000";
const username = process.env.ADMIN_WEB_SMOKE_USERNAME || "確認管理者";
const password = process.env.ADMIN_WEB_SMOKE_PASSWORD || "SmokeTest123!";
const periodMonth = process.env.ADMIN_WEB_SMOKE_MONTH || "2026-01";
const outputDir = new URL("../artifacts/screenshots/", import.meta.url);

function outputPath(fileName) {
  return fileURLToPath(new URL(fileName, outputDir));
}

async function setMonthIfPresent(page) {
  const monthInput = page.getByLabel("対象月");
  if (await monthInput.count()) {
    await monthInput.fill(periodMonth);
    await page.waitForTimeout(500);
  }
}

async function capture(page, path, fileName, readyText) {
  await page.goto(`${baseUrl}${path}`, { waitUntil: "networkidle" });
  await setMonthIfPresent(page);
  if (readyText) {
    await page.getByText(readyText).first().waitFor({ state: "visible", timeout: 10000 });
  }
  await page.screenshot({
    path: outputPath(fileName),
    fullPage: true,
  });
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
await page.screenshot({
  path: outputPath("01-login.png"),
  fullPage: true,
});

await page.getByLabel("ユーザー名").fill(username);
await page.getByLabel("パスワード").fill(password);
await page.getByRole("button", { name: "ログイン" }).click();
await page.waitForURL("**/dashboard");

await capture(page, "/dashboard", "02-dashboard.png", "差異アサイン");
await capture(page, "/billing/invoices", "03-invoices.png", "請求番号");
await capture(page, "/audit-logs", "04-audit-logs.png", "操作");
await capture(page, "/operations/csv-import", "05-csv-import.png", "CSVを取り込む");

await browser.close();