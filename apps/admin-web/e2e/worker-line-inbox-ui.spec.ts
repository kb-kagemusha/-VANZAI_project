import { expect, test, type Page } from "@playwright/test";

test.use({ viewport: { width: 1366, height: 900 } });

async function setupInbox(page: Page, options: { role?: string; listError?: boolean; conflict?: boolean; missingProfile?: boolean; profileError?: boolean } = {}) {
  let approved = false;
  let profileName: string | null = null;
  const calls: string[] = [];
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-admin-token"));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return respond({ id: "test-admin", username: "test-admin", display_name: "試験管理者", role: options.role || "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-admin-token", refresh_token: "mock-refresh-token", token_type: "bearer" });
    if (path === "/api/order-requests/line-links/test-worker/refresh-profile") {
      if (options.profileError) return respond({ detail: "LINE表示名を取得できませんでした。" }, 502);
      profileName = "LINEのサンプル名";
      return respond({ worker_id: "test-worker", line_display_name: profileName });
    }
    if (path === "/api/order-requests/line-links" && options.missingProfile) {
      return respond({ items: [{ worker_id: "test-worker", worker_name: "酒井 サンプル", line_display_name: profileName, linked_at: "2026-10-13T01:00:00Z" }] });
    }
    if (path === "/api/registration-requests") {
      expect(url.searchParams.get("line_only")).toBe("true");
      expect(url.searchParams.get("status")).toBe("pending");
      expect(url.searchParams.get("request_type")).toBe("worker");
      if (options.listError) return respond({ detail: "取得失敗" }, 500);
      return respond({ items: approved ? [] : [{ id: "test-request", summary_name: "酒井 サンプル", status: "pending", submitted_at: "2026-10-13T01:00:00Z" }], total: approved ? 0 : 1, offset: 0, limit: 30 });
    }
    if (path.startsWith("/api/line/registration/reviews/")) {
      calls.push(path);
      if (path.endsWith("/approve")) {
        expect(route.request().postDataJSON().comparison_ticket).toBe("review-ticket");
        if (options.conflict) return respond({ detail: "内容が変わりました。最新の内容を読み込んでください。" }, 409);
        approved = true;
        return respond({ request_id: "test-request", status: "approved", worker_id: "test-worker" });
      }
      const chosen = path.endsWith("/choice");
      return respond({ request_id: "test-request", status: approved ? "approved" : "pending", mode: chosen || approved ? "create_new" : "choose", can_decide: chosen && !approved, comparison_ticket: chosen ? "review-ticket" : null, before: {}, after: { name: "酒井 サンプル" }, components: { last_name: "酒井", first_name: "サンプル" }, candidates: [] });
    }
    if (path === "/api/workers") {
      calls.push(`workers:${approved}`);
      return respond({ items: approved ? [{ id: "test-worker", name: "酒井 サンプル", is_active: true, tags: [] }] : [], total: approved ? 1 : 0, offset: 0, limit: 30 });
    }
    return respond({ items: [], total: 0, offset: 0, limit: 30 });
  });
  await page.goto("/masters/workers");
  return calls;
}

test("LINE request appears before approval and moves to workers without a page reload", async ({ page }) => {
  const calls = await setupInbox(page);
  const inbox = page.locator("section").filter({ has: page.getByRole("heading", { name: "LINE登録・確認待ち（1件）" }) });
  await expect(inbox.getByText("酒井 サンプル", { exact: true })).toBeVisible();
  await expect(page.getByText("稼働者が見つかりません")).toBeVisible();
  expect(calls.some((path) => path.endsWith("/approve"))).toBe(false);
  await page.screenshot({ path: "../../artifacts/worker-line-inbox-pending.png", fullPage: true });
  await inbox.getByRole("button", { name: "内容を確認・反映" }).click();
  const dialog = page.getByRole("dialog", { name: "LINE登録の内容確認" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await dialog.getByRole("button", { name: "新規の稼働者として比較する" }).click();
  await expect(dialog.getByText("変更後: 酒井 サンプル")).toBeVisible();
  await page.screenshot({ path: "../../artifacts/worker-line-review-modal.png", fullPage: false });
  await dialog.getByRole("button", { name: "承認", exact: true }).click();
  await expect(page.getByRole("heading", { name: "LINE登録・確認待ち（0件）" })).toBeVisible();
  await expect(page.getByText("この申請の審査は終わっています。")).toBeVisible();
  await expect(page.locator("tr").filter({ hasText: "酒井 サンプル" })).toHaveCount(1);
  expect(calls).toContain("workers:true");
  await dialog.getByRole("button", { name: "閉じる", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.screenshot({ path: "../../artifacts/worker-line-inbox-approved.png", fullPage: true });
});

test("conflicting approval keeps the request pending and does not create a worker", async ({ page }) => {
  const calls = await setupInbox(page, { conflict: true });
  await page.getByRole("button", { name: "内容を確認・反映" }).click();
  await page.getByRole("button", { name: "新規の稼働者として比較する" }).click();
  await page.getByRole("button", { name: "承認", exact: true }).click();
  await expect(page.getByText("内容が変わりました。最新の内容を読み込んでください。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "LINE登録・確認待ち（1件）" })).toBeVisible();
  expect(calls).not.toContain("workers:true");
});

test("ops can see pending requests but cannot start an approval", async ({ page }) => {
  const calls = await setupInbox(page, { role: "ops" });
  await expect(page.getByRole("heading", { name: "LINE登録・確認待ち（1件）" })).toBeVisible();
  await expect(page.getByText("管理者が承認します", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "内容を確認・反映" })).toHaveCount(0);
  expect(calls.some((path) => path.includes("/reviews/"))).toBe(false);
});

test("a failed request load is not presented as an empty inbox", async ({ page }) => {
  await setupInbox(page, { listError: true });
  await expect(page.getByText("LINE登録申請を取得できませんでした。申請を更新してください。")).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("LINEの確認待ち申請はありません")).toHaveCount(0);
});

test("review popup closes with Escape and returns keyboard focus", async ({ page }) => {
  await setupInbox(page);
  const opener = page.getByRole("button", { name: "内容を確認・反映" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "LINE登録の内容確認" });
  await expect(dialog).toBeFocused();
  await expect(dialog.getByRole("button", { name: "新規の稼働者として比較する" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "閉じる", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByPlaceholder("却下理由")).toBeFocused();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("hidden");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  expect(await page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
});

test("an unavailable LINE name is retrieved into the existing link", async ({ page }) => {
  await setupInbox(page, { missingProfile: true });
  const links = page.locator("section").filter({ has: page.getByRole("heading", { name: "公式LINEの本人紐付け" }) });
  await expect(links.getByText("未取得", { exact: true })).toBeVisible();
  await expect(links.getByText("表示名なし", { exact: true })).toHaveCount(0);
  await links.getByRole("button", { name: "表示名を更新" }).click();
  await expect(links.getByText("LINEのサンプル名", { exact: true })).toBeVisible();
  await expect(links.getByText("LINE表示名を更新しました。", { exact: true })).toBeVisible();
});

test("a failed LINE profile lookup does not present a made-up name", async ({ page }) => {
  await setupInbox(page, { missingProfile: true, profileError: true });
  const links = page.locator("section").filter({ has: page.getByRole("heading", { name: "公式LINEの本人紐付け" }) });
  await links.getByRole("button", { name: "表示名を更新" }).click();
  await expect(links.getByText("LINE表示名を取得できませんでした。", { exact: true })).toBeVisible();
  await expect(links.getByText("未取得", { exact: true })).toBeVisible();
  await expect(links.getByText("LINEのサンプル名", { exact: true })).toHaveCount(0);
});
