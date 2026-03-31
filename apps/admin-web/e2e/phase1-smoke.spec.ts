import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

const username = process.env.ADMIN_WEB_SMOKE_USERNAME || "admin_web_smoke";
const password = process.env.ADMIN_WEB_SMOKE_PASSWORD || "SmokeTest123!";
const periodMonth = process.env.ADMIN_WEB_SMOKE_MONTH || "2026-01";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("ユーザー名").fill(username);
  await page.getByLabel("パスワード").fill(password);
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function setMonthIfPresent(page: Page) {
  const monthInput = page.getByLabel("対象月");
  const count = await monthInput.count();
  for (let index = 0; index < count; index += 1) {
    await monthInput.nth(index).fill(periodMonth);
  }
}

async function expectTableOrEmpty(page: Page) {
  const tableRows = page.locator("tbody tr");
  const emptyState = page.locator(".empty-state");
  await expect(tableRows.or(emptyState).first()).toBeVisible();
}

test("phase1 admin routes render with local data", async ({ page }) => {
  await login(page);

  await expect(page.getByRole("heading", { level: 2, name: "ダッシュボード" })).toBeVisible();
  await setMonthIfPresent(page);
  await expect(page.getByText("差異アサイン")).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "月次一括生成" })).toBeVisible();
  await expect(page.getByRole("button", { name: "月次一括生成" })).toBeVisible();
  await expect(page.getByRole("link", { name: "請求ログを見る" })).toBeVisible();
  await expect(page.getByRole("link", { name: "支払ログを見る" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "締め処理" })).toBeVisible();
  const closingSection = page.locator(".upload-card").nth(1);
  await expect(closingSection.getByRole("link", { name: "締め関連ログ" })).toBeVisible();
  await expect(closingSection.getByRole("link", { name: "締め実行ログ" })).toBeVisible();
  await expect(closingSection.getByRole("link", { name: "締め解除ログ" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "仮締め", exact: true })).toBeDisabled();
  await expect(closingSection.getByRole("button", { name: "本締め", exact: true })).toBeDisabled();
  await expect(closingSection.getByRole("button", { name: "一覧へ入力コピー" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "選択行へ入力コピー" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "未締めを選択" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "仮締め済みを選択" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "本締め済みを選択" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "解除候補を選択", exact: true })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "承認者未入力の必須行を選択" })).toBeVisible();
  await expect(closingSection.getByRole("button", { name: "理由未入力の解除候補を選択" })).toBeVisible();
  await expect(page.getByText("コピー対象")).toBeVisible();
  await expect(page.getByText("承認者入力")).toBeVisible();
  await expect(page.getByText("理由入力")).toBeVisible();
  await expect(page.getByText("選択状態")).toBeVisible();
  await expect(page.getByRole("link", { name: "監査ログ" }).first()).toBeVisible();

  const routes = [
    { path: "/operations/csv-import", heading: "CSV取込", readyText: "CSVを取り込む", expectsTable: false },
    { path: "/operations/actuals", heading: "実績一覧", expectsTable: true },
    { path: "/operations/assignments", heading: "アサイン一覧", expectsTable: true },
    { path: "/billing/invoices", heading: "請求一覧", expectsTable: true },
    { path: "/billing/payouts", heading: "支払一覧", expectsTable: true },
    { path: "/masters/prices", heading: "単価一覧", expectsTable: true },
    { path: "/audit-logs", heading: "監査ログ", expectsTable: true },
    { path: "/operations/projects", heading: "案件一覧", expectsTable: true },
    { path: "/operations/shift-slots", heading: "シフト枠一覧", expectsTable: true },
    { path: "/billing/expenses", heading: "経費一覧", expectsTable: true },
  ];

  for (const route of routes) {
    await page.goto(route.path);
    await expect(page.getByRole("heading", { level: 2, name: route.heading })).toBeVisible();
    await setMonthIfPresent(page);
    if (route.readyText) {
      await expect(page.getByText(route.readyText)).toBeVisible();
    }
    if (route.path === "/billing/invoices") {
      await expect(page.getByText("請求書を生成")).toBeVisible();
      await expect(page.getByRole("button", { name: "請求書生成" })).toBeDisabled();
    }
    if (route.path === "/billing/payouts") {
      await expect(page.getByText("支払明細を生成")).toBeVisible();
      await expect(page.getByRole("button", { name: "支払明細生成" })).toBeDisabled();
    }
    if (route.path === "/masters/prices") {
      await expect(page.getByRole("button", { name: "売上単価" })).toBeVisible();
      await expect(page.getByRole("button", { name: "外注単価" })).toBeVisible();
      await expect(page.getByRole("button", { name: "単価ルール" })).toBeVisible();
    }
    if (route.path === "/audit-logs") {
      const auditProjectSelect = page.locator("label").filter({ hasText: /^案件/ }).locator("select");
      await expect(page.getByText("クイックフィルタ")).toBeVisible();
      await expect(auditProjectSelect).toBeVisible();
      await expect(page.getByRole("button", { name: "締め関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "締め実行のみ" })).toBeVisible();
      await expect(page.getByRole("button", { name: "締め解除のみ" })).toBeVisible();
      await expect(page.getByRole("button", { name: "取込関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "実績関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "アサイン関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "単価関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "請求関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "支払関連" })).toBeVisible();
      await expect(page.getByRole("button", { name: "条件をクリア" })).toBeVisible();
      await expect(page.getByText("選択中:")).toBeVisible();
    }
    if (route.expectsTable) {
      await expectTableOrEmpty(page);
    }
  }

  await page.goto("/audit-logs?period_key=202601&quick_filter=closing_release&actor=admin_web_smoke&page=1");
  await expect(page.getByLabel("対象月")).toHaveValue("2026-01");
  await expect(page.getByLabel("対象種別")).toHaveValue("closing");
  await expect(page.getByLabel("実行者")).toHaveValue("admin_web_smoke");
  await expect(page.getByText("選択中: 締め解除のみ")).toBeVisible();
  await expect(page.getByRole("button", { name: "クイック: 締め解除のみ ×" })).toBeVisible();
  await expect(page.getByRole("button", { name: "実行者: admin_web_smoke ×" })).toBeVisible();
  await expect(page.getByRole("button", { name: "条件をクリア" })).toBeVisible();

  await page.goto("/audit-logs?period_key=202601");
  await expect(page.locator("label").filter({ hasText: /^操作種別/ }).locator('optgroup[label="請求・支払"]')).toHaveCount(1);
  await expect(page.locator("label").filter({ hasText: /^対象種別/ }).locator('optgroup[label="月次運用"]')).toHaveCount(1);
  await page.getByLabel("操作種別").selectOption("invoice_issued");
  await page.getByLabel("対象種別").selectOption("project");
  await expect(page.getByLabel("操作種別")).toHaveValue("invoice_issued");
  await expect(page.getByLabel("対象種別")).toHaveValue("project");
  await expect(page.getByRole("button", { name: "操作: 請求書発行 ×" })).toBeVisible();
  await expect(page.getByRole("button", { name: "対象: 案件 ×" })).toBeVisible();

  await page.goto("/audit-logs?period_key=202601&quick_filter=invoice_all");
  await expect(page.getByLabel("対象種別")).toHaveValue("invoice");
  await expect(page.getByText("選択中: 請求関連")).toBeVisible();
  await expect(page.getByRole("button", { name: "クイック: 請求関連 ×" })).toBeVisible();

  await page.goto("/audit-logs?period_key=202601&quick_filter=import_all");
  await expect(page.getByLabel("対象種別")).toHaveValue("import_batch");
  await expect(page.getByText("選択中: 取込関連")).toBeVisible();
  await expect(page.getByRole("button", { name: "クイック: 取込関連 ×" })).toBeVisible();

  await page.goto("/audit-logs?period_key=202601&quick_filter=price_all");
  await expect(page.getByLabel("対象種別")).toHaveValue("");
  await expect(page.getByText("選択中: 単価関連")).toBeVisible();
  await expect(page.getByText("単価ルール変更と単価解決をまとめて確認します。 単価ルール、売上単価、外注単価、アサインを含みます。")).toBeVisible();
  await expect(page.getByRole("button", { name: "クイック: 単価関連 ×" })).toBeVisible();

  await page.goto("/audit-logs?period_key=202601&quick_filter=payout_all");
  await expect(page.getByLabel("対象種別")).toHaveValue("payout");
  await expect(page.getByText("選択中: 支払関連")).toBeVisible();
  await expect(page.getByRole("button", { name: "クイック: 支払関連 ×" })).toBeVisible();

  await page.goto("/audit-logs?period_key=202601");
  await expect(page.locator("label").filter({ hasText: /^対象種別/ }).locator('option[value="price_sales"]')).toHaveCount(1);
  await expect(page.locator("label").filter({ hasText: /^対象種別/ }).locator('option[value="price_outsource"]')).toHaveCount(1);

  await page.goto("/audit-logs?period_key=202601&quick_filter=closing_all&project_id=proj-match");
  await expect(page.getByLabel("対象種別")).toHaveValue("closing");
  await expect(page.getByRole("button", { name: "クイック: 締め関連 ×" })).toBeVisible();
  await expect(page.getByRole("button", { name: /案件:/ })).toBeVisible();
  await expect(page.getByText(/案件 .* を中心に、対象月、操作種別、実行者、日付範囲で監査ログを検索します。/)).toBeVisible();
});