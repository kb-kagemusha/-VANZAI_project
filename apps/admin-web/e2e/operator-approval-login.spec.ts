import { expect, test } from "@playwright/test";

test("approval requires a pre-created free ID and can refresh after ID creation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let created = false;
  let approved = false;
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-token"));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = { items: [], total: 0 };
    if (path.endsWith("/auth/me")) body = { id: "admin", username: "admin", role: "admin", is_active: true };
    if (path.endsWith("/auth/session")) body = { access_token: "mock-token", token_type: "bearer" };
    if (path === "/api/registration-requests") body = { items: approved ? [] : [{ id: "request", request_type: "operator_staff", summary_name: "承認待ち本人", status: "pending", submitted_at: "2026-10-26T02:00:00Z" }], total: approved ? 0 : 1 };
    if (path === "/api/operator-registration/request") body = { request_id: "request", status: "pending", name: "承認待ち本人", phone: "09012345678", line_display_name: "本人LINE", staff_id: null, candidates: [], login_candidates: created ? [{ id: "precreated-id", username: "operator-login", display_name: "本人ID", staff_id: null }] : [] };
    if (path.endsWith("/request/approve")) {
      expect(route.request().postDataJSON().user_id).toBe("precreated-id");
      approved = true; body = { status: "approved", staff_id: "operator" };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/masters/registration-pending");
  await page.getByRole("button", { name: "内容を確認・反映" }).click();
  const dialog = page.getByRole("dialog", { name: "運営スタッフ登録の内容確認" });
  const approve = dialog.getByRole("button", { name: "IDを紐付けて承認", exact: true });
  await expect(approve).toBeDisabled();
  await expect(dialog.getByText("選べる未紐付けのIDがありません。先に本人のIDを作成してください。", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("link", { name: "IDを先に作成（別タブ）" })).toHaveAttribute("href", "/settings/access?create=1");
  created = true;
  await dialog.getByRole("button", { name: "ID一覧を更新" }).click();
  await dialog.getByRole("combobox", { name: "紐付けるログインID" }).selectOption("precreated-id");
  await expect(approve).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "../../.work/operator-ID-approval-mobile.png", fullPage: true });
  await approve.click();
  await expect(dialog).toHaveCount(0);
});

test("ID creation link waits for roles before opening the creation form", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-token"));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = { items: [], total: 0 };
    if (path.endsWith("/auth/me")) body = { id: "admin", username: "admin", role: "admin", is_active: true };
    if (path.endsWith("/auth/session")) body = { access_token: "mock-token", token_type: "bearer" };
    if (path === "/api/access/roles") body = { available_permissions: [], roles: [
      { role: "admin", display_name: "全体管理者", permissions: [], default_permissions: [], editable: false },
      { role: "site_manager", display_name: "現場管理者", permissions: [], default_permissions: [], editable: true },
    ] };
    await route.fulfill({ json: body });
  });
  await page.goto("/settings/access?create=1");
  const dialog = page.getByRole("dialog", { name: "ログインIDを作成" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("combobox", { name: "役割", exact: true })).toHaveValue("site_manager");
});
