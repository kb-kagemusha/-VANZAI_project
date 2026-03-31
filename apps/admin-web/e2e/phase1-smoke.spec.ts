import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined>; platform: string };

const username = process.env.ADMIN_WEB_SMOKE_USERNAME || "admin_web_smoke";
const password = process.env.ADMIN_WEB_SMOKE_PASSWORD || "SmokeTest123!";
const periodMonth = process.env.ADMIN_WEB_SMOKE_MONTH || "2026-01";
const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const pythonPath = fileURLToPath(
  new URL(process.platform === "win32" ? "../../../.venv/Scripts/python.exe" : "../../../.venv/bin/python", import.meta.url),
);
const ensureLocalAdminScript = fileURLToPath(new URL("../../../scripts/ensure_local_admin.py", import.meta.url));
const ensureBrowserSmokeDataScript = fileURLToPath(new URL("../../../scripts/ensure_browser_smoke_data.py", import.meta.url));

function runSetupScript(scriptPath: string) {
  execFileSync(pythonPath, [scriptPath], { cwd: repoRoot, stdio: "inherit" });
}

test.beforeAll(() => {
  runSetupScript(ensureLocalAdminScript);
  runSetupScript(ensureBrowserSmokeDataScript);
});

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
  await expect(page.locator(".summary-card").filter({ hasText: "送信先未設定支払" })).toContainText(/送信先未設定支払\s*[1-9]\d*/);
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
    { path: "/operations/assignment-responses", heading: "予定確認監視", expectsTable: true },
    { path: "/billing/invoices", heading: "請求一覧", expectsTable: true },
    { path: "/billing/payouts", heading: "支払一覧", expectsTable: true },
    { path: "/masters/prices", heading: "単価一覧", expectsTable: true },
    { path: "/masters/data", heading: "マスタ一覧", expectsTable: true },
    { path: "/audit-logs", heading: "監査ログ", expectsTable: true },
    { path: "/operations/projects", heading: "案件一覧", expectsTable: true },
    { path: "/operations/shift-slots", heading: "シフト枠", expectsTable: true },
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
      await expect(page.locator(".summary-card").filter({ hasText: "送信先未設定支払" })).toContainText(/送信先未設定支払\s*[1-9]\d*/);
      await expect(page.getByText("既定送信先未設定のみ")).toBeVisible();
      const smokePayoutRow = page.locator("tbody tr").filter({ hasText: "Browser Smoke Missing Recipient Worker" }).first();
      await expect(smokePayoutRow).toBeVisible();
      await smokePayoutRow.getByRole("button", { name: "履歴" }).click();
      await expect(page.getByText("送信候補")).toBeVisible();
      await expect(page.getByRole("button", { name: /履歴送信先: smoke-recipient@example.com/ })).toBeVisible();
    }
    if (route.path === "/masters/prices") {
      await expect(page.getByRole("button", { name: "売上単価" })).toBeVisible();
      await expect(page.getByRole("button", { name: "外注単価" })).toBeVisible();
      await expect(page.getByRole("button", { name: "単価ルール" })).toBeVisible();
    }
    if (route.path === "/masters/data") {
      await expect(page.getByRole("button", { name: "稼働者", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "下請け", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "クライアント", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "現場", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "案件種別", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "役割", exact: true })).toBeVisible();
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
  await expect(page.locator("tbody")).toContainText("送信先: smoke-recipient@example.com");
  await expect(page.locator("tbody")).toContainText("送信理由: スモーク確認送信");
  await expect(page.locator("tbody")).toContainText("内部メモ: 監査ログ要約確認用");

  await page.goto("/audit-logs?period_key=202601");
  await expect(page.locator("label").filter({ hasText: /^対象種別/ }).locator('option[value="price_sales"]')).toHaveCount(1);
  await expect(page.locator("label").filter({ hasText: /^対象種別/ }).locator('option[value="price_outsource"]')).toHaveCount(1);

  await page.goto("/audit-logs?period_key=202601&quick_filter=closing_all&project_id=proj-match");
  await expect(page.getByLabel("対象種別")).toHaveValue("closing");
  await expect(page.getByRole("button", { name: "クイック: 締め関連 ×" })).toBeVisible();
  await expect(page.getByRole("button", { name: /案件:/ })).toBeVisible();
  await expect(page.getByText(/案件 .* を中心に、対象月、操作種別、実行者、日付範囲で監査ログを検索します。/)).toBeVisible();
});

test("phase1 admin can resend and escalate assignment responses", async ({ page }) => {
  await login(page);

  await page.goto("/operations/assignment-responses");
  await expect(page.getByRole("heading", { level: 2, name: "予定確認監視" })).toBeVisible();
  await setMonthIfPresent(page);
  await page.getByLabel("稼働者").selectOption({ label: "Browser Smoke Response Worker" });

  const smokeRow = page
    .locator("tbody tr")
    .filter({ hasText: "Browser Smoke Payout Project" })
    .filter({ hasText: "Browser Smoke Response Worker" })
    .filter({ hasText: "Smoke Pending Response" })
    .first();
  await expect(smokeRow).toBeVisible();
  await expect(page.getByText("直近催促履歴")).toBeVisible();
  await expect(page.getByText("直近エスカレーション履歴")).toBeVisible();

  await smokeRow.getByRole("button", { name: "再送" }).click();
  await expect(page.getByText(/催促送信を実行しました: 対象1件 \/ sent 1 \/ failed 0/)).toBeVisible();
  await expect(page.locator("section.card").filter({ hasText: "直近催促履歴" })).toContainText("送信済み");
  await expect(page.locator("section.card").filter({ hasText: "直近催促履歴" })).toContainText("Browser Smoke Response Worker / smoke-assignment-worker@example.com");

  await smokeRow.getByRole("button", { name: "通知" }).click();
  await expect(page.getByText(/エスカレーション通知を実行しました: 対象1件 \/ recipient \d+ \/ sent \d+ \/ failed 0/)).toBeVisible();
  await expect(page.locator("section.card").filter({ hasText: "直近エスカレーション履歴" })).toContainText("送信済み");
});

test("phase1 admin can manage assignment operations", async ({ page }) => {
  test.slow();
  const selectionSetName = `Browser Smoke Selection ${Date.now()}`;

  await login(page);

  await page.goto("/operations/assignments");
  await expect(page.getByRole("heading", { level: 2, name: "アサイン一覧" })).toBeVisible();
  await setMonthIfPresent(page);

  const rowCheckbox = page.getByLabel("Browser Smoke Ops Worker / Browser Smoke Payout Project を選択").first();
  const assignmentRow = rowCheckbox.locator("xpath=ancestor::tr[1]");

  await expect(assignmentRow).toBeVisible();
  await expect(assignmentRow).toContainText("Smoke Ops Assignment");

  await assignmentRow.getByRole("button", { name: "編集" }).click();
  const editCard = page.locator("section.card").filter({ hasText: "編集: Browser Smoke Ops Worker / Browser Smoke Payout Project" }).first();
  await editCard.getByLabel("売上単価").fill("34567");
  await editCard.getByLabel("外注単価").fill("23456");
  await editCard.getByRole("button", { name: "アサインを更新" }).click();
  await expect(assignmentRow).toContainText("34,567");
  await expect(assignmentRow).toContainText("23,456");

  await assignmentRow.getByRole("button", { name: "状態変更" }).click();
  const statusCard = page.locator("section.card").filter({ hasText: "状態変更: Browser Smoke Ops Worker / Browser Smoke Payout Project" }).first();
  await statusCard.getByLabel("変更先状態").selectOption("canceled");
  await statusCard.getByLabel("取消理由").fill("browser smoke cancel reason");
  await statusCard.getByRole("button", { name: "状態を更新" }).click();
  await expect(assignmentRow).toContainText("取消");

  const cancellationSection = page.locator("section.card").filter({ hasText: "取消履歴" }).first();
  await expect(cancellationSection).toContainText("browser smoke cancel reason");
  const cancellationRow = cancellationSection.locator("tbody tr").filter({ hasText: "Browser Smoke Ops Worker" }).first();
  await cancellationRow.getByRole("button", { name: "再開" }).click();

  const reopenCard = page.locator("section.card").filter({ hasText: "再開 / 状態変更: Browser Smoke Ops Worker / Browser Smoke Payout Project" }).first();
  await reopenCard.getByLabel("変更先状態").selectOption("confirmed");
  await reopenCard.getByLabel("復帰理由").fill("browser smoke reopen reason");
  await reopenCard.getByRole("button", { name: "再開する" }).click();
  await expect(assignmentRow).toContainText("確定");

  await rowCheckbox.check();
  await page.getByLabel("保存セット名").fill(selectionSetName);
  await page.getByRole("button", { name: "現在の選択を保存" }).click();
  await expect(page.getByText(selectionSetName)).toBeVisible();

  await page.getByRole("button", { name: "すべて解除" }).click();
  await expect(rowCheckbox).not.toBeChecked();
  const selectionSetCard = page.locator("strong").filter({ hasText: selectionSetName }).first().locator("xpath=ancestor::div[2]");
  await selectionSetCard.getByRole("button", { name: "読み込む" }).click();
  await expect(rowCheckbox).toBeChecked();

  await page.getByLabel("変更先状態").last().selectOption("tentative");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "選択中アサインを更新" }).click();
  await expect(assignmentRow).toContainText("仮確定");

  await assignmentRow.getByRole("button", { name: "状態変更" }).click();
  const confirmCard = page.locator("section.card").filter({ hasText: "状態変更: Browser Smoke Ops Worker / Browser Smoke Payout Project" }).first();
  await confirmCard.getByLabel("変更先状態").selectOption("confirmed");
  await confirmCard.getByRole("button", { name: "状態を更新" }).click();
  await expect(assignmentRow).toContainText("確定");

  const refreshedSelectionSetCard = page.locator("strong").filter({ hasText: selectionSetName }).first().locator("xpath=ancestor::div[2]");
  await refreshedSelectionSetCard.getByRole("button", { name: "削除" }).click();
  await expect(page.getByText(selectionSetName)).toHaveCount(0);
});

test("phase1 admin can create and update master and price records", async ({ page }) => {
  test.slow();
  const uniqueSuffix = Date.now().toString();
  const supplierName = `Browser Smoke Supplier ${uniqueSuffix}`;
  const supplierEmail = `supplier-${uniqueSuffix}@example.com`;
  const supplierPhone = `090-${uniqueSuffix.slice(-4)}-${uniqueSuffix.slice(-4)}`;
  const updatedSupplierPhone = `080-${uniqueSuffix.slice(-4)}-${uniqueSuffix.slice(-4)}`;
  const ruleName = `Browser Smoke Rule ${uniqueSuffix}`;
  const updatedRuleName = `${ruleName} Updated`;
  const salesPrice = String(21000 + Number(uniqueSuffix.slice(-3)));
  const updatedSalesPrice = String(Number(salesPrice) + 111);
  const outsourcePrice = String(12000 + Number(uniqueSuffix.slice(-3)));
  const updatedOutsourcePrice = String(Number(outsourcePrice) + 222);
  const formatYen = (value: string) => `￥${Number(value).toLocaleString("ja-JP")}`;

  await login(page);

  await page.goto("/masters/data");
  await page.getByRole("button", { name: "下請け" }).click();

  const masterCreateCard = page.locator("section.card").filter({ hasText: "下請けを追加" }).first();
  await masterCreateCard.getByLabel("名称").fill(supplierName);
  await masterCreateCard.getByLabel("メール").fill(supplierEmail);
  await masterCreateCard.getByLabel("電話").fill(supplierPhone);
  await masterCreateCard.getByRole("button", { name: "下請けを追加" }).click();
  await expect(page.getByText("下請けを作成しました")).toBeVisible();

  await page.getByLabel("検索").fill(supplierName);
  const supplierRow = page.locator("tbody tr").filter({ hasText: supplierName }).first();
  await expect(supplierRow).toBeVisible();
  await supplierRow.getByRole("button", { name: "編集" }).click();

  const masterEditCard = page.locator("section.card").filter({ hasText: "下請けを編集" }).first();
  await masterEditCard.getByLabel("電話").fill(updatedSupplierPhone);
  await masterEditCard.getByRole("button", { name: "更新する" }).click();
  await expect(page.getByText("下請けを更新しました")).toBeVisible();
  await expect(supplierRow).toContainText(updatedSupplierPhone);

  await page.goto("/masters/prices");
  await page.getByRole("button", { name: "単価ルール" }).click();

  const priceCreateCard = page.locator("section.card").filter({ hasText: "単価を追加" }).first();
  await priceCreateCard.getByLabel("ルール名").fill(ruleName);
  await priceCreateCard.getByLabel("優先順位").fill("15");
  await priceCreateCard.getByLabel("売上単価").fill("15000");
  await priceCreateCard.getByLabel("外注単価").fill("9000");
  await priceCreateCard.getByRole("button", { name: "追加する" }).click();
  await expect(page.getByText("単価を作成しました")).toBeVisible();

  await page.getByLabel("検索").fill(ruleName);
  const ruleRow = page.locator("tbody tr").filter({ hasText: ruleName }).first();
  await expect(ruleRow).toBeVisible();
  await ruleRow.getByRole("button", { name: "編集" }).click();

  const priceEditCard = page.locator("section.card").filter({ hasText: "単価を編集" }).first();
  await priceEditCard.getByLabel("ルール名").fill(updatedRuleName);
  await priceEditCard.getByLabel("優先順位").fill("5");
  await priceEditCard.getByRole("button", { name: "更新する" }).click();
  await expect(page.getByText("単価を更新しました")).toBeVisible();

  await page.getByLabel("検索").fill(updatedRuleName);
  const updatedRuleRow = page.locator("tbody tr").filter({ hasText: updatedRuleName }).first();
  await expect(updatedRuleRow).toBeVisible();
  await expect(updatedRuleRow).toContainText("5");

  await page.getByRole("button", { name: "売上単価", exact: true }).click();

  const salesCreateCard = page.locator("section.card").filter({ hasText: "単価を追加" }).first();
  await salesCreateCard.getByRole("textbox", { name: "単価", exact: true }).fill(salesPrice);
  await salesCreateCard.getByRole("button", { name: "追加する" }).click();
  await expect(page.getByText("単価を作成しました")).toBeVisible();

  const salesRow = page.locator("tbody tr").filter({ hasText: formatYen(salesPrice) }).first();
  await expect(salesRow).toBeVisible();
  await salesRow.getByRole("button", { name: "編集" }).click();

  const salesEditCard = page.locator("section.card").filter({ hasText: "単価を編集" }).first();
  await salesEditCard.getByRole("textbox", { name: "単価", exact: true }).fill(updatedSalesPrice);
  await salesEditCard.getByRole("button", { name: "更新する" }).click();
  await expect(page.getByText("単価を更新しました")).toBeVisible();
  await expect(page.locator("tbody tr").filter({ hasText: formatYen(updatedSalesPrice) }).first()).toBeVisible();

  await page.getByRole("button", { name: "外注単価", exact: true }).click();

  const outsourceCreateCard = page.locator("section.card").filter({ hasText: "単価を追加" }).first();
  await outsourceCreateCard.getByRole("textbox", { name: "単価", exact: true }).fill(outsourcePrice);
  await outsourceCreateCard.getByRole("button", { name: "追加する" }).click();
  await expect(page.getByText("単価を作成しました")).toBeVisible();

  const outsourceRow = page.locator("tbody tr").filter({ hasText: formatYen(outsourcePrice) }).first();
  await expect(outsourceRow).toBeVisible();
  await outsourceRow.getByRole("button", { name: "編集" }).click();

  const outsourceEditCard = page.locator("section.card").filter({ hasText: "単価を編集" }).first();
  await outsourceEditCard.getByRole("textbox", { name: "単価", exact: true }).fill(updatedOutsourcePrice);
  await outsourceEditCard.getByRole("button", { name: "更新する" }).click();
  await expect(page.getByText("単価を更新しました")).toBeVisible();
  await expect(page.locator("tbody tr").filter({ hasText: formatYen(updatedOutsourcePrice) }).first()).toBeVisible();
});

test("phase1 admin can create and update projects and shift slots", async ({ page }) => {
  test.slow();
  const uniqueSuffix = Date.now().toString();
  const projectName = `Browser Smoke Project ${uniqueSuffix}`;
  const updatedProjectName = `${projectName} Updated`;
  const projectCode = `BSP${uniqueSuffix.slice(-6)}`;
  const updatedProjectCode = `BSU${uniqueSuffix.slice(-6)}`;
  const projectNote = `project-note-${uniqueSuffix}`;
  const updatedProjectNote = `project-note-updated-${uniqueSuffix}`;
  const shiftLabel = `日勤-${uniqueSuffix.slice(-4)}`;
  const updatedShiftLabel = `遅番-${uniqueSuffix.slice(-4)}`;
  const shiftNote = `shift-note-${uniqueSuffix}`;
  const updatedShiftNote = `shift-note-updated-${uniqueSuffix}`;
  const workDate = `${periodMonth}-15`;
  const updatedWorkDate = `${periodMonth}-16`;

  await login(page);

  await page.goto("/operations/projects");
  const projectCreateCard = page.locator("section.card").filter({ hasText: "案件を作成" }).first();
  await projectCreateCard.getByLabel("案件名").fill(projectName);
  await projectCreateCard.getByLabel("コード").fill(projectCode);
  await projectCreateCard.getByLabel("取引先").selectOption({ index: 1 });
  await projectCreateCard.getByLabel("開始日").fill(workDate);
  await projectCreateCard.getByLabel("終了日").fill(updatedWorkDate);
  await projectCreateCard.getByLabel("メモ").fill(projectNote);
  await projectCreateCard.getByRole("button", { name: "案件を作成" }).click();

  await page.getByLabel("検索").fill(projectName);
  const projectRow = page.locator("tbody tr").filter({ hasText: projectName }).first();
  await expect(projectRow).toBeVisible();
  await projectRow.getByRole("button", { name: "編集" }).click();

  const projectEditCard = page.locator("section.card").filter({ hasText: "案件を編集" }).first();
  await projectEditCard.getByLabel("案件名").fill(updatedProjectName);
  await projectEditCard.getByLabel("コード").fill(updatedProjectCode);
  await projectEditCard.getByLabel("メモ").fill(updatedProjectNote);
  await projectEditCard.getByRole("button", { name: "更新する" }).click();
  await expect(page.getByText("案件を更新しました")).toBeVisible();

  await page.getByLabel("検索").fill(updatedProjectName);
  const updatedProjectRow = page.locator("tbody tr").filter({ hasText: updatedProjectName }).first();
  await expect(updatedProjectRow).toBeVisible();
  await expect(updatedProjectRow).toContainText(updatedProjectCode);
  await expect(updatedProjectRow).toContainText(updatedProjectNote);

  await page.goto("/operations/shift-slots");
  const shiftMonth = await page.getByLabel("対象月").inputValue();
  const shiftWorkDate = `${shiftMonth}-15`;
  const updatedShiftWorkDate = `${shiftMonth}-16`;
  const shiftCreateCard = page.locator("section.card").filter({ hasText: "シフト枠を作成" }).first();
  await shiftCreateCard.getByLabel("案件").selectOption({ label: updatedProjectName });
  await shiftCreateCard.getByLabel("稼働日").fill(shiftWorkDate);
  await shiftCreateCard.getByLabel("開始時刻").fill("09:00");
  await shiftCreateCard.getByLabel("終了時刻").fill("18:00");
  await shiftCreateCard.getByLabel("シフトラベル").fill(shiftLabel);
  await shiftCreateCard.getByLabel("必要人数").fill("2");
  await shiftCreateCard.getByLabel("メモ").fill(shiftNote);
  await shiftCreateCard.getByRole("button", { name: "シフト枠を作成" }).click();

  await page.locator(".filter-bar label").filter({ hasText: /^案件/ }).locator("select").selectOption({ label: updatedProjectName });
  await page.getByLabel("検索").fill("");
  const shiftRow = page.locator("tbody tr").first();
  await expect(shiftRow).toBeVisible();
  await shiftRow.getByRole("button", { name: "編集" }).click();

  const shiftEditCard = page.locator("section.card").filter({ hasText: "シフト枠を編集" }).first();
  await shiftEditCard.getByLabel("稼働日").fill(updatedShiftWorkDate);
  await shiftEditCard.getByLabel("開始時刻").fill("10:00");
  await shiftEditCard.getByLabel("終了時刻").fill("19:00");
  await shiftEditCard.getByLabel("シフトラベル").fill(updatedShiftLabel);
  await shiftEditCard.getByLabel("必要人数").fill("3");
  await shiftEditCard.getByLabel("メモ").fill(updatedShiftNote);
  await shiftEditCard.getByRole("button", { name: "更新する" }).click();

  await page.getByLabel("検索").fill("");
  const updatedShiftRow = page.locator("tbody tr").first();
  await expect(updatedShiftRow).toBeVisible();
  await expect(updatedShiftRow).toContainText(updatedShiftNote);
  await expect(updatedShiftRow).toContainText("3");
});