import { expect, test, type Page } from "@playwright/test";

test.use({ viewport: { width: 1440, height: 1000 } });

async function mockApi(page: Page, withNote = false) {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  let active = withNote;
  let voided = false;
  const writes: unknown[] = [];
  const note = { id: "n1", schedule_entry_id: "e1", series_id: "s1", worker_id: "w1", work_date: "2026-10-12",
    project_name: "秋の会場イベント", worker_name: "佐藤 花子", is_test: false, kind: "late", cause: "personal", late_minutes: 120,
    summary: "2時間遅刻", payment_note: "遅刻時の支払額を確認してください", reason: "現場責任者から到着遅れの報告",
    reported_by: "現場ディレクター", actor_name: "運営担当", created_at: "2026-10-12T10:00:00Z", voided_at: null, void_reason: null };
  const payout = { id: "p1", payout_number: "PAY-1", payee_name: "佐藤 花子", payee_type: "worker", recipient_type: "worker", recipient_id: "w1",
    project_id: "pr1", project_name: "秋の会場イベント", period_key: "202610", version: 1, status: "preparing", total_amount: "18000",
    has_pdf: false, default_recipient_email: "sato@example.com" };
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "a1", username: "admin", role: "admin", is_active: true, permissions: [] });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/attendance-notes/events")) return reply({ items: [{ series_id: "s1", project_name: "秋の会場イベント" }] });
    if (path.endsWith("/attendance-notes/schedules")) return reply({ items: [{ id: "e1", worker_id: "w1", worker_name: "佐藤 花子", start_time: "09:00:00", status: "active" }] });
    if (path.endsWith("/attendance-notes/payment-summary")) return reply({ total: active && !voided ? 1 : 0, payouts: active && !voided ? { p1: { worker_id: "w1", count: 1 } } : {} });
    if (path.endsWith("/attendance-notes/n1/void")) { voided = true; writes.push(route.request().postDataJSON()); return reply({ ...note, voided_at: "2026-10-24T09:00:00Z", void_reason: "対象者を訂正" }); }
    if (path.endsWith("/attendance-notes")) {
      if (route.request().method() === "POST") { active = true; writes.push(route.request().postDataJSON()); return reply(note, 201); }
      const include = active && (!voided || url.searchParams.get("include_voided") === "true") && (!url.searchParams.get("worker_id") || url.searchParams.get("worker_id") === "w1");
      return reply({ items: include ? [{ ...note, voided_at: voided ? "2026-10-24T09:00:00Z" : null, void_reason: voided ? "対象者を訂正" : null }] : [], total: include ? 1 : 0, limit: 50, offset: 0 });
    }
    if (path.endsWith("/payouts")) return reply({ items: [payout], total: 1, limit: 20, offset: 0 });
    if (path.endsWith("/order-billing/summary")) return reply({ total: 0, missing_count: 0 });
    return reply({ items: [], total: 0 });
  });
  return { writes };
}

test("records an accepted worker's lateness in a modal and preserves void history", async ({ page }, info) => {
  const state = await mockApi(page);
  await page.goto("/operations/attendance-notes");
  await page.getByLabel("対象月", { exact: true }).fill("2026-10");
  await expect(page.getByRole("link", { name: "遅刻・キャンセル記録", exact: true })).toBeVisible();
  await expect(page.getByLabel("報告者（現場責任者など）")).toHaveCount(0);
  await page.getByRole("button", { name: "記録を登録", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "遅刻・キャンセルを記録" });
  await dialog.getByRole("combobox", { name: "イベント", exact: true }).selectOption("s1");
  await dialog.getByLabel("稼働日", { exact: true }).fill("2026-10-12");
  await dialog.getByRole("combobox", { name: "稼働予定者", exact: true }).selectOption("e1");
  await dialog.getByLabel("遅刻時間（分）").fill("120");
  await dialog.getByLabel("報告者（現場責任者など）").fill("現場ディレクター");
  await dialog.getByLabel("理由・報告内容").fill("現場責任者から到着遅れの報告");
  await dialog.getByRole("button", { name: "記録を登録する" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("cell", { name: /2時間遅刻/ })).toBeVisible();
  expect(state.writes[0]).toEqual({ schedule_entry_id: "e1", kind: "late", cause: "personal", late_minutes: 120, reported_by: "現場ディレクター", reason: "現場責任者から到着遅れの報告" });
  await page.screenshot({ path: info.outputPath("attendance-list.png"), fullPage: true });
  await page.getByRole("button", { name: "記録を取り消す" }).click();
  const cancel = page.getByRole("dialog", { name: "記録の取り消し" });
  await cancel.getByLabel("取消理由").fill("対象者を訂正");
  await cancel.getByRole("button", { name: "取り消しを確定する" }).click();
  await page.getByLabel("取消済みも表示").check();
  await expect(page.getByText("取消済み：対象者を訂正")).toBeVisible();
});

test("payment warning precedes amount and explains the same worker's monthly event reports", async ({ page }, info) => {
  await mockApi(page, true);
  await page.goto("/billing/payouts");
  await expect(page.getByRole("button", { name: "注意事項あり（1件）", exact: true })).toBeVisible();
  const headers = await page.getByRole("columnheader").allTextContents();
  expect(headers.indexOf("支払前の注意事項")).toBeLessThan(headers.indexOf("合計"));
  await page.getByRole("button", { name: "注意事項あり（1件）", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "月次支払の注意事項" });
  await expect(dialog).toContainText("2026-10-12／秋の会場イベント／佐藤 花子：2時間遅刻");
  await expect(dialog).toContainText("この支払明細の合計");
  const positions = await dialog.evaluate(el => {
    const text = el.textContent ?? "";
    return [text.indexOf("2時間遅刻"), text.indexOf("この支払明細の合計")];
  });
  expect(positions[0]).toBeLessThan(positions[1]);
  await page.screenshot({ path: info.outputPath("payment-warning.png"), fullPage: true });
});

test("warning retrieval failure is never displayed as no warnings", async ({ page }) => {
  await mockApi(page, true);
  await page.route("**/api/attendance-notes/payment-summary?**", route => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "failed" }) }));
  await page.goto("/billing/payouts");
  await expect(page.getByRole("alert")).toContainText("注意事項を取得できません");
  await expect(page.getByRole("cell", { name: "取得失敗・要確認" })).toBeVisible();
});
