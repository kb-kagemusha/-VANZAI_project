import { expect, test } from "@playwright/test";

test("test filter persists across four calendars and category color is stable", async ({ page }, testInfo) => {
  page.on("pageerror", (error) => console.log("PAGE ERROR:", error.message));
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const events = [
    { series_id: "festival", project_name: "フェステスト", categories: ["フェス系", "研修"] },
    { series_id: "training", project_name: "研修テスト", categories: ["研修"] },
  ].map((e) => ({ ...e, version_id: e.series_id, document_number: e.series_id, is_test: true,
    ok: [{ worker_id: "w1", name: "ダミー稼働者" }], changing: [], unanswered: [] }));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (url.pathname.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    const include = url.searchParams.get("include_test") === "true";
    if (url.pathname.endsWith("/participation-calendar")) return reply({ workers: [{ worker_id: "w1", name: "ダミー稼働者", line_linked: false }],
      days: include ? [{ date: "2026-10-10", events }] : [] });
    if (url.pathname.endsWith("/availability-calendar")) return reply({ date_from: "2026-10-01", date_to: "2026-10-31",
      workers: [{ id: "w1", name: "ダミー稼働者", is_active: true, tags: ["newcomer"],
        days: { "2026-10-10": { availability_status: "available_all_day", assignments: [], order_events: include ? events.map((e) => ({ ...e, status: "ok" })) : [] } } }] });
    return reply({ items: [], total: 0, missing_count: 0 });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/operations/calendar?view=event&month=2026-10");
  await page.screenshot({ path: testInfo.outputPath("initial.png"), fullPage: true });
  await expect(page.getByText("この月に依頼済みのイベントはありません。")).toBeVisible();
  await page.getByRole("button", { name: "テストも表示", exact: true }).click();
  await expect(page.locator(".ov-event-box.ov-c3")).toContainText("フェステスト");
  await expect(page.locator(".ov-event-box.ov-c6")).toContainText("研修テスト");
  await expect(page.locator(".overview-row-name .test-data-badge")).toHaveCount(2);
  for (const name of ["稼働者ごと", "参加カレンダー", "出勤可能日"]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(page.getByRole("button", { name: "テストも表示", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".ov-c3").filter({ hasText: "フェステスト" }).first()).toBeVisible();
  }
  await page.getByRole("button", { name: "正式のみ", exact: true }).click();
  await expect(page.getByText("フェステスト", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "テストも表示", exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath("availability-demo.png"), fullPage: true });
});

test("billing test orders are opt-in and labelled in amount dialog", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const row = { version_id: "v1", series_id: "s1", document_number: "TEST-001", version_no: 1, is_test: true,
    project_name: "金額確認テスト", work_date_label: "2026年11月1日", categories: ["研修"], client_id: "c1", client_name: "ダミー依頼元",
    revision: 0, amount_id: null, amount: null, billing_month: null, invoice_id: null, status: "missing", incentive_enabled: false,
    incentive_note: "インセンティブなし", incentive_amount: null, total_amount: null, billing_ready: false, client_mismatch: false };
  let saved = false;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (url.pathname.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (url.pathname.endsWith("/orders/v1/confirm")) { saved = true; return reply({ id: "amount1", revision: 1 }); }
    if (url.pathname.endsWith("/order-billing/orders")) {
      const items = url.searchParams.get("include_test") === "true" && !saved ? [row] : [];
      return reply({ items, total: items.length });
    }
    return reply({ items: [], total: 0, missing_count: 0 });
  });
  await page.goto("/billing/order-amounts");
  await expect(page.getByText("該当する依頼書はありません。")).toBeVisible();
  await page.getByRole("checkbox", { name: "テストも含む" }).check();
  await expect(page.locator(".order-list-table .test-data-badge")).toBeVisible();
  await page.getByRole("button", { name: "請求金額を確定", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "依頼書の請求金額を確定" });
  await expect(dialog.locator(".test-data-badge")).toBeVisible();
  await dialog.getByLabel("請求月（必須）").fill("2026-11");
  await dialog.getByLabel("通常請求額（インセンティブを除く・税抜・円）", { exact: true }).fill("200000");
  await dialog.getByRole("button", { name: "請求金額を確定する", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(saved).toBe(true);
});
