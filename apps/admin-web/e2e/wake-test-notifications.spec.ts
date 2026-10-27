import { expect, test, type Page } from "@playwright/test";

async function setup(page: Page, role = "admin", conflict = false) {
  let state = { enabled: false, enabled_from: null as string | null, enabled_until: null as string | null, revision: 0, updated_at: null as string | null, updated_by: null as string | null };
  const writes: unknown[] = [];
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-admin-token"));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (json: unknown, status = 200) => route.fulfill({status, json});
    if (path.endsWith("/auth/me")) return respond({ id: "test-admin", username: "test-admin", display_name: "試験管理者", role, is_active: true, permissions: ["wake_status_read"] });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-admin-token", refresh_token: "mock-refresh-token", token_type: "bearer" });
    if (path === "/api/line-daily/test-notification-settings") {
      if (route.request().method() === "PUT") {
        const body = route.request().postDataJSON(); writes.push(body);
        if (conflict) return respond({ detail: "別の画面で設定が変更されました。最新の設定を読み直してください。" }, 409);
        state = {...state, ...body, revision: state.revision + 1, enabled_from: body.enabled ? new Date().toISOString() : null, updated_by: "test-admin", updated_at: new Date().toISOString()};
      }
      return respond(state);
    }
    if (path === "/api/line-daily/wake-status") return respond({date: "2026-10-27", total: 0, reported: 0, items: []});
    return respond({items: [], total: 0});
  });
  return writes;
}

test("admin enables with expiry then disables; form only appears in dialog", async ({page}) => {
  await page.setViewportSize({width: 1280, height: 900});
  const writes = await setup(page);
  await page.goto("/operations/wake-status");
  const section = page.getByRole("region", {name: "テスト通知の設定"});
  await expect(section.getByRole("status")).toHaveText("送らない");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", {name: "テスト通知を設定", exact: true}).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", {name: "送る（期限付き）", exact: true}).click();
  await expect(dialog.getByLabel("終了時刻（日本時間）", {exact: true})).toBeVisible();
  await expect(dialog.getByText("有効な間は実際にLINEを送信し", {exact: false})).toBeVisible();
  await page.screenshot({path: "../../.work/wake-test-notification-settings.png", fullPage: true});
  await dialog.getByRole("button", {name: "設定を保存", exact: true}).click();
  await expect(dialog).toHaveCount(0);
  await expect(section.getByRole("status")).toContainText("送る：");
  expect(writes[0]).toMatchObject({enabled: true, revision: 0});
  await page.getByRole("button", {name: "テスト通知を設定", exact: true}).click();
  await dialog.getByRole("button", {name: "送らない", exact: true}).click();
  await dialog.getByRole("button", {name: "設定を保存", exact: true}).click();
  await expect(section.getByRole("status")).toHaveText("送らない");
  expect(writes[1]).toMatchObject({enabled: false, enabled_until: null, revision: 1});
});

test("conflict preserves draft and offers explicit refresh", async ({page}) => {
  await setup(page, "admin", true);
  await page.goto("/operations/wake-status");
  await page.getByRole("button", {name: "テスト通知を設定", exact: true}).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", {name: "送る（期限付き）", exact: true}).click();
  await dialog.getByRole("button", {name: "設定を保存", exact: true}).click();
  await expect(dialog.getByRole("alert")).toContainText("別の画面");
  await expect(dialog.getByRole("button", {name: "送る（期限付き）", exact: true})).toHaveAttribute("aria-pressed", "true");
  await dialog.getByRole("button", {name: "最新の設定を読み直す"}).click();
  await expect(dialog.getByRole("button", {name: "送らない", exact: true})).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("button", {name: "テスト通知を設定", exact: true})).toBeFocused();
});

test("ops cannot see notification settings", async ({page}) => {
  await setup(page, "ops");
  await page.goto("/operations/wake-status");
  await expect(page.getByRole("heading", {name: "起床状況", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "テスト通知を設定", exact: true})).toHaveCount(0);
});
