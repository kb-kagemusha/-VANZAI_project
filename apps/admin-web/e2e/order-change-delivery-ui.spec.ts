import { test, expect } from "@playwright/test";

test("changed orders remain prominent and send only after confirmation", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  let sent = 0;
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url()), path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (data: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/change-delivery-pending/d1/send")) { sent++; return reply({ send_status: "accepted" }); }
    if (path.endsWith("/change-delivery-pending")) return reply({ total: 1, pending_people: sent ? 2 : 3, line_send_available: true, items: [{
      version_id: "v2", document_number: "REQ-002", project_name: "秋のフェス", kind: "formal", version_no: 2,
      recipients: [...(sent ? [] : [{ delivery_id: "d1", worker_name: "長谷川 亜香里", send_status: "unsent", line_linked: true, can_send: true }]),
        { delivery_id: "d2", worker_name: "渡邊 健太郎", send_status: "unknown", line_linked: true, can_send: false },
        { delivery_id: "d3", worker_name: "山田 太郎", send_status: "failed", line_linked: false, can_send: false }],
    }] });
    return reply({ items: [], total: 0 });
  });
  await page.goto("/operations/order-requests");
  const notice = page.getByRole("complementary", { name: "変更版の送付待ち" });
  await expect(notice).toContainText("3人（1件）");
  await notice.getByRole("button", { name: "対象者を確認・送付" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("長谷川 亜香里", { exact: true })).toBeVisible();
  await expect(dialog.getByText("結果不明・要確認", { exact: true })).toBeVisible();
  await expect(dialog.getByText("送信失敗・LINE未連携", { exact: true })).toBeVisible();
  await expect(dialog.locator("li").nth(1).getByRole("button", { name: "変更版を送付" })).toBeDisabled();
  await expect(dialog.locator("li").nth(2).getByRole("button", { name: "変更版を送付" })).toBeDisabled();
  await dialog.locator("li").first().getByRole("button", { name: "変更版を送付" }).click();
  expect(sent).toBe(0);
  await page.getByRole("button", { name: "送付する", exact: true }).click();
  await expect(dialog.getByRole("status")).toContainText("本人の返事はまだです");
  expect(sent).toBe(1);
  await expect(notice).toContainText("2人（1件）");
  await expect(dialog.locator("li")).toHaveCount(2);
  await page.screenshot({ path: test.info().outputPath("change-delivery-warning.png"), fullPage: true });
});
