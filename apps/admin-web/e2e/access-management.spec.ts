import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function mockAdmin(page: Page) {
  const roles = ["admin", "ops", "accounting", "site_manager"].map((role, index) => ({role,
    display_name: ["全体管理者", "運用担当", "経理担当", "現場管理者"][index], editable: role !== "admin",
    permissions: ["project_read"], default_permissions: ["project_read"], builtin: true}));
  const captured: { account?: Record<string, unknown>; policy?: Record<string, unknown>; role?: Record<string, unknown> } = {};
  await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "test-access"); localStorage.setItem("vanzai.admin.refresh_token", "test-refresh"); });
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const url = new URL(route.request().url());
    let body: unknown = {items: [], total: 0, offset: 0, limit: 50};
    if (url.pathname === "/api/auth/me") body = {username: "admin", display_name: "全体管理者", role: "admin", email: "admin@example.com", is_active: true, permissions: [], can_use_admin_console: true};
    if (url.pathname === "/api/access/roles" && route.request().method() === "POST") {
      captured.role = route.request().postDataJSON();
      roles.push({role: "r_custom", display_name: String(captured.role?.display_name), editable: true, permissions: captured.role?.permissions as string[], default_permissions: [], builtin: false});
      body = roles[roles.length - 1];
    } else if (url.pathname === "/api/access/roles") body = {available_permissions: ["project_read", "invoice_read"], roles};
    if (url.pathname === "/api/access/users" && route.request().method() === "POST") {captured.account = route.request().postDataJSON(); body = {id: "new", ...captured.account};}
    if (url.pathname === "/api/access/roles/site_manager") {captured.policy = route.request().postDataJSON(); body = captured.policy;}
    if (url.pathname === "/api/dashboard") body = {unprocessed_items: [], variance_alerts: [], closing_status: []};
    if (url.pathname.endsWith("/project-types/tree")) body = {items: []};
    if (url.pathname.endsWith("/worker-tags")) body = {options: []};
    await route.fulfill({status: 200, contentType: "application/json", body: JSON.stringify(body)});
  });
  return captured;
}

test("administrator creates an ID and changes role permissions in popups", async ({page}) => {
  const captured = await mockAdmin(page);
  await page.goto("/settings/access");
  await expect(page.getByRole("heading", {name: "ID・権限管理"})).toBeVisible();
  await expect(page.getByLabel("ログインID", {exact: true})).toHaveCount(0);
  await page.getByRole("button", {name: "新しいIDを作成", exact: true}).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("ログインID", {exact: true}).fill("manager01");
  await dialog.getByLabel("表示名", {exact: true}).fill("現場担当");
  await dialog.getByLabel("メールアドレス", {exact: true}).fill("manager@example.com");
  await dialog.getByLabel("初期パスワード", {exact: true}).fill("password123");
  await dialog.getByRole("button", {name: "IDを作成", exact: true}).click();
  await expect(dialog).toHaveCount(0);
  expect(captured.account?.role).toBe("site_manager");
  await page.getByRole("button", {name: "役割ごとの権限", exact: true}).click();
  await page.getByRole("row").filter({hasText: "現場管理者"}).getByRole("button", {name: "権限を編集"}).click();
  await dialog.getByLabel("請求：閲覧", {exact: true}).check();
  await dialog.getByLabel("変更理由", {exact: true}).fill("請求の確認担当を兼任");
  await dialog.getByRole("button", {name: "この役割の権限を保存"}).click();
  await expect.poll(() => captured.policy?.permissions).toEqual(["project_read", "invoice_read"]);
  await expect(dialog).toHaveCount(0);
});

test("custom role is created in a popup and can be selected for new IDs", async ({page}) => {
  const captured = await mockAdmin(page);
  await page.goto("/settings/access");
  await page.getByRole("button", {name: "役割ごとの権限", exact: true}).click();
  await page.getByRole("button", {name: "新しい役割を作成", exact: true}).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("役割名", {exact: true}).fill("案件閲覧担当");
  await expect(dialog.getByLabel("案件：閲覧", {exact: true})).not.toBeChecked();
  await dialog.getByLabel("案件：閲覧", {exact: true}).check();
  await dialog.getByLabel("変更理由", {exact: true}).fill("案件の確認を分担");
  await page.screenshot({path: "test-results/custom-role-popup.png", fullPage: true});
  await dialog.getByRole("button", {name: "役割を作成", exact: true}).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("cell", {name: "案件閲覧担当", exact: true})).toBeVisible();
  expect(captured.role?.permissions).toEqual(["project_read"]);
  await page.getByRole("button", {name: "ログインID", exact: true}).click();
  await page.getByRole("button", {name: "新しいIDを作成", exact: true}).click();
  await dialog.getByLabel("役割", {exact: true}).selectOption({label: "案件閲覧担当"});
  await expect(dialog.getByLabel("役割", {exact: true})).toHaveValue("r_custom");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

for (const [path, button, title] of [
  ["/operations/projects", "新しい案件を作成", "案件を作成"],
  ["/operations/shift-slots", "新しいシフト枠を作成", "シフト枠を作成"],
  ["/operations/assignments", "新しい配置を作成", "配置を作成"],
  ["/billing/invoices", "請求書を生成", "請求書を生成"],
  ["/billing/payouts", "支払明細を生成", "支払明細を生成"],
  ["/masters/prices", "単価を新規作成", "単価の作成・編集"],
  ["/operations/notices", "＋ 通知を作成", "通知を作成"],
  ["/operations/registration-requests", "登録リンクを発行", "登録リンクを発行"],
]) {
  test("record form is a popup: " + path, async ({page}) => {
    await mockAdmin(page);
    await page.goto(path);
    const action = page.getByRole("button", {name: button, exact: true});
    await expect(action).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await action.click();
    const dialog = page.getByRole("dialog", {name: title, exact: true});
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("input,select,textarea").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(action).toBeFocused();
  });
}

for (const role of ["site_manager", "r_custom"]) {
  test("read-only user keeps forbidden pages and creation hidden: " + role, async ({page}) => {
    await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "test-access"); localStorage.setItem("vanzai.admin.refresh_token", "test-refresh"); });
    await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
      const path = new URL(route.request().url()).pathname;
      let body: unknown = {items: [], total: 0, limit: 20, offset: 0};
      if (path === "/api/auth/me") body = {username: "manager", display_name: "確認担当", role, role_name: "案件閲覧担当", can_use_admin_console: true, email: "manager@example.com", is_active: true, permissions: ["project_read", "dashboard_read", "master_read"]};
      if (path === "/api/dashboard") body = {unprocessed_items: [], variance_alerts: [], closing_status: []};
      await route.fulfill({status: 200, contentType: "application/json", body: JSON.stringify(body)});
    });
    await page.goto("/dashboard");
    await expect(page.locator(".side-nav").getByText("案件閲覧担当", {exact: true})).toBeVisible();
    await expect(page.locator(".side-nav").getByRole("link", {name: "請求一覧", exact: true})).toHaveCount(0);
    await page.goto("/operations/projects");
    await expect(page.getByRole("heading", {name: "案件一覧", exact: true})).toBeVisible();
    await expect(page.getByRole("button", {name: "新しい案件を作成", exact: true})).toHaveCount(0);
    await page.goto("/settings/access"); await expect(page).toHaveURL(/\/403$/);
    await page.goto("/billing/invoices"); await expect(page).toHaveURL(/\/403$/);
  });
}

test("popup remains usable on a narrow screen and preserves values on API errors", async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await mockAdmin(page);
  await page.route("**/api/access/users", async route => {
    if (route.request().method() === "POST") await route.fulfill({status: 409, contentType: "application/json", body: JSON.stringify({detail: "このログインIDは既に登録されています"})});
    else await route.fallback();
  });
  await page.goto("/settings/access");
  await page.getByRole("button", {name: "新しいIDを作成", exact: true}).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("ログインID", {exact: true}).fill("existing");
  await dialog.getByLabel("表示名", {exact: true}).fill("確認担当");
  await dialog.getByLabel("メールアドレス", {exact: true}).fill("existing@example.com");
  await dialog.getByLabel("初期パスワード", {exact: true}).fill("password123");
  const bounds = await dialog.boundingBox();
  expect(bounds?.x).toBeGreaterThanOrEqual(0);
  expect((bounds?.x ?? 0) + (bounds?.width ?? 0)).toBeLessThanOrEqual(390);
  await dialog.getByRole("button", {name: "IDを作成", exact: true}).click();
  await expect(dialog.getByRole("alert")).toHaveText("このログインIDは既に登録されています");
  await expect(dialog.getByLabel("ログインID", {exact: true})).toHaveValue("existing");
  await page.screenshot({path: "test-results/id-popup-mobile.png", fullPage: true});
});
