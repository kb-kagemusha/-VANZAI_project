import { expect, test } from "@playwright/test";

test("sent requests are grouped by document and both lists paginate and show tests", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const all = Array.from({ length: 55 }, (_, i) => ({ document_id: `doc${i}`, version_id: `v${i}`, document_number: `REQ-${String(i).padStart(3, "0")}`,
    kind: i % 2 ? "formal" : "test", version_no: 1, project_name: `イベント${i}`, categories: ["フェス系"], status: "confirmed", work_date_label: "10月25〜27日", created_by_name: "担当者",
    recipient_count: 3, change_documents: [], recipients: ["acked", "unacked", "declined"].map((ack_status, j) => ({ delivery_id: `d${i}-${j}`, worker_name: ["渡邊 健太郎", "長谷川 亜香里", "山田 太郎"][j], ack_status, send_status: "accepted", version_no: 1 })) }));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/reply-groups") || path === "/api/order-requests") {
      const kind = url.searchParams.get("kind") || "all";
      const pool = all.filter((row) => kind === "all" || row.kind === kind);
      const limit = Number(url.searchParams.get("limit") || 10), offset = Number(url.searchParams.get("offset") || 0);
      return reply({ items: pool.slice(offset, offset + limit), total: pool.length, limit, offset, line_send_available: false });
    }
    return reply({ items: [], total: 0 });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/operations/order-requests");
  const sent = page.locator(".order-list-frame.is-sent"), created = page.locator(".order-list-frame.is-created");
  await expect(sent.locator("tbody > tr")).toHaveCount(10);
  await expect(created.locator("tbody > tr")).toHaveCount(10);
  const first = sent.locator("tbody > tr").first();
  await expect(first.getByRole("button", { name: "REQ-000", exact: true })).toHaveCount(1);
  await expect(first.locator(".order-reply-recipients li")).toHaveCount(3);
  await expect(first.locator(".order-reply-status")).toHaveText(["受諾", "未回答", "辞退"]);
  await expect(created.locator("tbody > tr").first().locator(".test-data-badge")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("grouped-order-lists.png"), fullPage: true });
  await sent.getByRole("button", { name: "次へ", exact: true }).click();
  await expect(sent.getByRole("button", { name: "REQ-010", exact: true })).toBeVisible();
  await expect(created.getByRole("button", { name: "REQ-000", exact: true })).toBeVisible();
  await sent.getByLabel("送信した依頼の表示件数").selectOption("50");
  await expect(sent.locator("tbody > tr")).toHaveCount(50);
  await sent.getByRole("button", { name: "次へ", exact: true }).click();
  await expect(sent.locator("tbody > tr")).toHaveCount(5);
  await expect(sent.getByRole("button", { name: "次へ", exact: true })).toBeDisabled();
  await created.getByLabel("作成した依頼書の表示件数").selectOption("20");
  await expect(created.locator("tbody > tr")).toHaveCount(20);
  await created.getByRole("button", { name: "次へ", exact: true }).click();
  await expect(created.getByRole("button", { name: "REQ-020", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "テストのみ", exact: true }).click();
  await expect(sent.locator("tbody > tr")).toHaveCount(28);
  await expect(created.getByRole("button", { name: "REQ-000", exact: true })).toBeVisible();
  await expect(sent.locator("tbody > tr .test-data-badge")).toHaveCount(28);
});

test("master roster and worker registration use the same newcomer and director marks", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const workers = [{ id: "new", name: "石川 美月", is_active: true, tags: [], is_newcomer: true, is_director: false },
    { id: "director", name: "渡邊 健太郎", is_active: true, tags: ["director"], is_newcomer: false, is_director: true }];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/workers")) return reply({ items: workers, total: workers.length });
    if (path.endsWith("/worker-tags")) return reply({ items: [{ code: "director", label: "ディレクター可能" }] });
    return reply({ items: [], total: 0 });
  });
  for (const path of ["/masters/data", "/masters/workers"]) {
    await page.goto(path);
    const novice = page.getByRole("row").filter({ hasText: "石川 美月" });
    const director = page.getByRole("row").filter({ hasText: "渡邊 健太郎" });
    await expect(novice.getByRole("img", { name: "新人（稼働開始日から3か月）" })).toBeVisible();
    await expect(director.getByRole("img", { name: "ディレクター可能", exact: true })).toBeVisible();
    await expect(novice.getByRole("img", { name: "ディレクター可能", exact: true })).toHaveCount(0);
    await expect(director.getByRole("img", { name: "新人（稼働開始日から3か月）" })).toHaveCount(0);
  }
});
