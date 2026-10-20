import { expect, test } from "@playwright/test";

test("administrator creates an ID and changes role permissions", async ({ page }) => {
  let created: Record<string, unknown> | undefined;
  let configured: Record<string, unknown> | undefined;
  await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "test-access"); localStorage.setItem("vanzai.admin.refresh_token", "test-refresh"); });
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const url = new URL(route.request().url());
    let body: unknown = { items: [], total: 0, offset: 0, limit: 50 };
    if (url.pathname === "/api/auth/me") body = { username: "admin", display_name: "全体管理者", role: "admin", email: "admin@example.com", is_active: true, permissions: [] };
    if (url.pathname === "/api/access/users" && route.request().method() === "POST") { created = route.request().postDataJSON(); body = { id: "new", ...created }; }
    if (url.pathname === "/api/access/roles") body = {available_permissions: ["project_read", "invoice_read"], roles: ["admin", "ops", "accounting", "site_manager"].map(role => ({role, editable: role !== "admin", permissions: ["project_read"], default_permissions: ["project_read"]}))};
    if (url.pathname === "/api/access/roles/site_manager") { configured = route.request().postDataJSON(); body = configured; }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/settings/access");
  await expect(page.getByRole("heading", { name: "ID・権限管理" })).toBeVisible();
  await page.getByLabel("ログインID", { exact: true }).fill("manager01");
  await page.getByLabel("表示名", { exact: true }).fill("現場担当");
  await page.getByLabel("メールアドレス", { exact: true }).fill("manager@example.com");
  await page.getByLabel("初期パスワード", { exact: true }).fill("password123");
  await page.getByRole("button", { name: "IDを作成", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("保存しました");
  expect(created?.role).toBe("site_manager");
  await page.getByRole("button", { name: "役割ごとの権限", exact: true }).click();
  await page.getByLabel("請求：閲覧", { exact: true }).check();
  await page.getByLabel("変更理由", { exact: true }).fill("請求の確認担当を兼任");
  await page.getByRole("button", { name: "この役割の権限を保存" }).click();
  await expect.poll(() => configured?.permissions).toEqual(["project_read", "invoice_read"]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/access-management.png", fullPage: true });
});

test("field manager sees project menus and cannot open account or billing pages", async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "test-access"); localStorage.setItem("vanzai.admin.refresh_token", "test-refresh"); });
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = { items: [], total: 0, limit: 20, offset: 0 };
    if (path === "/api/auth/me") body = {username: "manager", display_name: "現場管理者", role: "site_manager", email: "manager@example.com", is_active: true, permissions: ["project_read", "dashboard_read", "shift_read", "master_read"]};
    if (path === "/api/dashboard") body = {unprocessed_items: [], variance_alerts: [], closing_status: []};
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "ダッシュボード" })).toBeVisible();
  await expect(page.locator(".side-nav").getByRole("link", {name: "案件一覧", exact: true})).toBeVisible();
  await expect(page.locator(".side-nav").getByRole("link", {name: "請求一覧", exact: true})).toHaveCount(0);
  await expect(page.locator(".side-nav").getByRole("link", {name: "ID・権限管理", exact: true})).toHaveCount(0);
  await page.goto("/operations/projects");
  await expect(page.getByRole("heading", {name: "案件一覧", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "案件を作成", exact: true})).toHaveCount(0);
  await page.goto("/settings/access");
  await expect(page).toHaveURL(/\/403$/);
  await page.goto("/billing/invoices");
  await expect(page).toHaveURL(/\/403$/);
});
