import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined>; platform: string };

const username = process.env.STAFF_MOBILE_SMOKE_USERNAME || "staff_mobile_smoke";
const password = process.env.STAFF_MOBILE_SMOKE_PASSWORD || "SmokeTest123!";
const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const pythonPath = fileURLToPath(
  new URL(process.platform === "win32" ? "../../../.venv/Scripts/python.exe" : "../../../.venv/bin/python", import.meta.url),
);
const ensureLocalWorkerScript = fileURLToPath(new URL("../../../scripts/ensure_local_worker.py", import.meta.url));
const ensureBrowserSmokeDataScript = fileURLToPath(new URL("../../../scripts/ensure_browser_smoke_data.py", import.meta.url));

function runSetupScript(scriptPath: string) {
  execFileSync(pythonPath, [scriptPath], { cwd: repoRoot, stdio: "inherit" });
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("ユーザー名").fill(username);
  await page.getByLabel("パスワード").fill(password);
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page).toHaveURL(/\/today$/);
}

function assignmentCard(page: Page, shiftLabel: string): Locator {
  return page.locator("article.assignment-card").filter({ hasText: shiftLabel }).first();
}

function actualCard(page: Page, projectName: string): Locator {
  return page.locator("article.actual-card").filter({ hasText: projectName }).first();
}

test.beforeAll(() => {
  runSetupScript(ensureBrowserSmokeDataScript);
  runSetupScript(ensureLocalWorkerScript);
});

test("phase5 worker can execute today, schedule, availability, expense, and actual flows", async ({ page }) => {
  test.slow();
  const expenseAmount = "1234";

  await login(page);

  await expect(page.getByText("今日の動き")).toBeVisible();
  const todayCard = assignmentCard(page, "Smoke Mobile Today");
  await expect(todayCard).toBeVisible();
  await todayCard.getByRole("button", { name: "出勤する" }).click();
  await expect(page.getByText("出勤を記録しました。")).toBeVisible();
  await expect(todayCard.getByRole("button", { name: "退勤する" })).toBeVisible();
  await todayCard.getByRole("button", { name: "退勤する" }).click();
  await expect(page.getByText("退勤を記録しました。")).toBeVisible();
  await expect(todayCard).toContainText("このアサインは退勤まで記録済みです。");

  await expect(page.locator(".mobile-nav-badge")).toContainText("1");
  await page.getByRole("link", { name: /予定/ }).click();
  await expect(page).toHaveURL(/\/schedule$/);
  const pendingCard = assignmentCard(page, "Smoke Mobile Pending Response");
  await expect(pendingCard).toBeVisible();
  await pendingCard.getByLabel("連絡メモ").fill("browser smoke response note");
  await pendingCard.getByRole("button", { name: "参加可で返信" }).click();
  await expect(page.getByText("予定確認を更新しました。")).toBeVisible();
  await expect(pendingCard).toContainText("参加可");
  await expect(page.locator(".mobile-nav-badge")).toHaveCount(0);

  await page.getByRole("link", { name: /可否/ }).click();
  await expect(page).toHaveURL(/\/availability$/);
  const availabilityCard = page.locator("article.actual-card").filter({ hasText: "2026/04/10" }).first();
  await expect(availabilityCard).toBeVisible();
  await availabilityCard.locator("select").selectOption("available");
  await availabilityCard.locator("textarea").fill("browser smoke availability note");
  await availabilityCard.getByRole("button", { name: "保存する" }).click();
  await expect(page.getByText("稼働可否を更新しました。")).toBeVisible();
  await expect(availabilityCard).toContainText("対応可");

  await page.getByRole("link", { name: /経費/ }).click();
  await expect(page).toHaveURL(/\/expenses$/);
  await page.getByLabel("金額").fill(expenseAmount);
  await page.getByLabel("内容").fill("browser smoke expense");
  await page.getByRole("button", { name: "経費を申請する" }).click();
  await expect(page.getByText("経費を申請しました。")).toBeVisible();
  await expect(page.locator(".list-section")).toContainText("￥1,234");

  await page.getByRole("link", { name: /実績/ }).click();
  await expect(page).toHaveURL(/\/actuals$/);
  const actualRow = actualCard(page, "Browser Smoke Mobile Project");
  await expect(actualRow).toBeVisible();
  await expect(actualRow).toContainText("Browser Smoke Mobile Role");
});