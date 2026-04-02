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

function formatSlashDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}/${month}/${day}`;
}

function currentAvailabilityDate() {
  const today = new Date();
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  return new Date(today.getFullYear(), today.getMonth(), Math.min(10, lastDay));
}

test.beforeAll(() => {
  runSetupScript(ensureBrowserSmokeDataScript);
  runSetupScript(ensureLocalWorkerScript);
});

test("phase5 worker can execute today, schedule, availability, expense, and actual flows", async ({ page }) => {
  test.slow();
  const expenseAmount = "1234";
  const availabilityDate = currentAvailabilityDate();
  const availabilityDateLabel = formatSlashDate(availabilityDate);

  await login(page);

  await expect(page.getByText("今日の動き")).toBeVisible();
  const todayCard = assignmentCard(page, "本日確認イベント");
  await expect(todayCard).toBeVisible();
  await todayCard.getByRole("button", { name: "出勤する" }).click();
  await expect(page.getByText("出勤を記録しました。")).toBeVisible();
  await expect(todayCard.getByRole("button", { name: "退勤する" })).toBeVisible();
  await todayCard.getByRole("button", { name: "退勤する" }).click();
  await expect(page.getByText("退勤を記録しました。")).toBeVisible();
  await expect(todayCard).toContainText("このアサインは退勤まで記録済みです。");

  await expect(page.locator(".mobile-nav-badge")).toContainText("1");
  await page.getByRole("link", { name: /^予定(\s+\d+)?$/ }).click();
  await expect(page).toHaveURL(/\/schedule$/);
  const pendingCard = assignmentCard(page, "確認待ちイベント");
  await expect(pendingCard).toBeVisible();
  await pendingCard.getByLabel("連絡メモ").fill("確認用連絡メモ");
  await pendingCard.getByRole("button", { name: "参加可で返信" }).click();
  await expect(page.getByText("予定確認を更新しました。")).toBeVisible();
  await expect(pendingCard).toContainText("参加可");
  await expect(page.locator(".mobile-nav-badge")).toHaveCount(0);

  await page.getByRole("link", { name: "事前予定" }).click();
  await expect(page).toHaveURL(/\/availability$/);
  const availabilityDay = page.getByRole("button", { name: new RegExp(availabilityDateLabel) }).first();
  await expect(availabilityDay).toBeVisible();
  await availabilityDay.click();
  await page.getByRole("button", { name: /補足を(入力|編集)/ }).click();
  await page.getByLabel("補足").fill("確認用事前予定メモ");
  await page.getByRole("button", { name: /候補と変更を保存|変更を保存/ }).click();
  await expect(page.getByText("事前予定を更新しました。")).toBeVisible();
  await expect(page.locator("article.actual-card").filter({ hasText: availabilityDateLabel })).toContainText("稼働OK（1日）");

  await page.getByRole("link", { name: "経費" }).click();
  await expect(page).toHaveURL(/\/expenses$/);
  await page.getByLabel("金額").fill(expenseAmount);
  await page.getByLabel("内容").fill("確認用経費メモ");
  await page.getByRole("button", { name: "経費を申請する" }).click();
  await expect(page.getByText("経費を申請しました。")).toBeVisible();
  await expect(page.locator(".list-section")).toContainText("￥1,234");

  await page.getByRole("link", { name: "実績" }).click();
  await expect(page).toHaveURL(/\/actuals$/);
  const actualRow = actualCard(page, "スタッフ確認案件");
  await expect(actualRow).toBeVisible();
  await expect(actualRow).toContainText("モバイル担当");
});