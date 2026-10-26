import { test, expect, type Page } from "@playwright/test";

async function publicForm(page: Page, enabled = true, failure = false) {
  const submitted: any[] = [];
  await page.addInitScript(() => { (window as any).liff = { init: async () => {}, isLoggedIn: () => true, login: () => {}, getIDToken: () => "verified-token" }; });
  await page.route("**/api/line/operator-registration/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/entry")) return route.fulfill({ contentType: "application/json", body: JSON.stringify({ enabled, liff_id: "1234567890-Test" }) });
    submitted.push(route.request().postDataJSON());
    return route.fulfill({ status: failure ? 409 : 200, contentType: "application/json", body: JSON.stringify(failure ? { detail: "運営スタッフの申請を確認中です。管理者の承認をお待ちください" } : { request_id: "op-request", status: "pending" }) });
  });
  await page.goto("/public/line-operator-registration?invite=long-invitation-token-for-tests-only");
  return submitted;
}

test("operator registers with only name and phone and confirms before submitting on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const submitted = await publicForm(page);
  await page.getByRole("textbox", { name: "氏名", exact: false }).fill("運営 太郎");
  await page.getByRole("textbox", { name: "電話番号", exact: false }).fill("０９０－１２３４－５６７８");
  await expect(page.locator("input")).toHaveCount(2);
  await expect(page.getByText("最寄り駅", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await expect(page.getByText("09012345678", { exact: true })).toBeVisible();
  expect(submitted).toHaveLength(0);
  await expect(page.getByText("運営スタッフ", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: ".work/operator-register-mobile.png" });
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toBeVisible();
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toMatchObject({ name: "運営 太郎", phone: "09012345678", id_token: "verified-token" });
  expect(submitted[0]).not.toHaveProperty("line_user_id");
});

test("unconfigured operator registration is closed without asking for worker details", async ({ page }) => {
  const submitted = await publicForm(page, false);
  await expect(page.getByRole("heading", { name: "ただいま準備中です" })).toBeVisible();
  await expect(page.locator("input")).toHaveCount(0);
  expect(submitted).toHaveLength(0);
});

test("a failed operator submission keeps input and does not claim success", async ({ page }) => {
  await publicForm(page, true, true);
  await page.getByRole("textbox", { name: "氏名", exact: false }).fill("運営 太郎");
  await page.getByRole("textbox", { name: "電話番号", exact: false }).fill("09012345678");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("alert")).toContainText("申請を確認中");
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toHaveCount(0);
  await page.getByRole("button", { name: "入力内容を修正する" }).click();
  await expect(page.getByRole("textbox", { name: "氏名", exact: false })).toHaveValue("運営 太郎");
});

test("shared pending inbox identifies both kinds, approves operator and decrements combined badge", async ({ page }) => {
  let approved = false;
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-token"));
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    let body: unknown = { items: [], total: 0 };
    if (path.endsWith("/auth/me")) body = { id: "admin", username: "admin", role: "admin", is_active: true };
    if (path.endsWith("/auth/session")) body = { access_token: "mock-token", token_type: "bearer" };
    if (path === "/api/registration-requests") {
      const worker = { id: "worker-request", request_type: "worker", summary_name: "稼働者 花子", status: "pending", submitted_at: "2026-10-26T01:00:00Z" };
      const operator = { id: "operator-request", request_type: "operator_staff", summary_name: "運営 太郎", status: "pending", submitted_at: "2026-10-26T02:00:00Z" };
      body = { items: approved ? [worker] : [operator, worker], total: approved ? 1 : 2 };
    }
    if (path === "/api/operator-registration/operator-request") body = { request_id: "operator-request", status: "pending", name: "運営 太郎", phone: "09012345678", line_display_name: "太郎のLINE", staff_id: null, candidates: [] };
    if (path.endsWith("/operator-request/approve") && method === "POST") { approved = true; body = { status: "approved", staff_id: "operator" }; }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/masters/registration-pending");
  const nav = page.getByRole("link", { name: "登録確認待ち 2件", exact: true });
  await expect(nav.locator(".nav-unread-badge")).toHaveText("2");
  const row = page.locator("tr").filter({ hasText: "運営 太郎" });
  await expect(row.getByText("運営スタッフ", { exact: true })).toBeVisible();
  await expect(page.locator("tr").filter({ hasText: "稼働者 花子" }).getByText("稼働者", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: "内容を確認・反映" }).click();
  const dialog = page.getByRole("dialog", { name: "運営スタッフ登録の内容確認" });
  await expect(dialog.getByText("09012345678", { exact: true })).toBeVisible();
  await page.screenshot({ path: ".work/operator-approval-dialog.png" });
  await dialog.getByRole("button", { name: "承認", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("link", { name: "登録確認待ち 1件", exact: true }).locator(".nav-unread-badge")).toHaveText("1");
  await expect(page.locator("tr").filter({ hasText: "運営 太郎" })).toHaveCount(0);
});

test("admin invite dialog stays disabled until LINE setup is ready", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-token"));
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith("/auth/me") ? { id: "admin", username: "admin", role: "admin", is_active: true } : path.endsWith("/auth/session") ? { access_token: "mock-token", token_type: "bearer" } : path.endsWith("/operator-registration/settings") ? { enabled: false } : { items: [], total: 0 };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/masters/operator-staff");
  await page.getByRole("button", { name: "LINE登録の招待リンク" }).click();
  const dialog = page.getByRole("dialog", { name: "運営スタッフのLINE招待" });
  await expect(dialog.getByRole("button", { name: "招待リンクを発行" })).toBeDisabled();
  await expect(dialog.getByText(/運営用LIFFの設定後/)).toBeVisible();
});
