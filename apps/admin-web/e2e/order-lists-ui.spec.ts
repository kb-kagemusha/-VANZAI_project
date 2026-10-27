import { expect, test } from "@playwright/test";

test("sent requests are grouped by document and both lists paginate and show tests", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const all = Array.from({ length: 55 }, (_, i) => ({ document_id: `doc${i}`, version_id: `v${i}`, document_number: `REQ-${String(i).padStart(3, "0")}`,
    kind: i % 2 ? "formal" : "test", version_no: 1, project_name: `イベント${i}`, categories: ["フェス系"], status: "confirmed", work_date_label: ["2026年10月25日～2026年10月27日", "2026年10月25日〜\n2026年10月27日", "2026年10月25日から2026年10月27日まで", "2026年10月4日〜2026年10月4日", "2026年10月4日"][i % 5], created_by_name: "担当者",
    recipient_count: 3, change_documents: [], recipients: ["acked", "unacked", "declined"].map((ack_status, j) => ({ delivery_id: `d${i}-${j}`, worker_name_snapshot: `【テスト】追加スタッフ0${j + 1}`, worker_name: ["渡邊 健太郎", "長谷川 亜香里", "山田 太郎"][j], ack_status, send_status: "accepted", version_no: 1 })) }));
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
  const selectStyle = async (selector: string) => page.getByLabel(selector).evaluate((el) => {
    const style = getComputedStyle(el); return [style.width, style.height, style.appearance, style.padding, style.backgroundImage, style.fontSize, style.borderRadius];
  });
  expect(await selectStyle("送信した依頼の表示件数")).toEqual(await selectStyle("作成した依頼書の表示件数"));
  const sizeTop = await created.getByLabel("作成した依頼書の表示件数").evaluate((el) => el.getBoundingClientRect().y);
  const queueTop = await created.getByLabel("依頼書の一覧条件").evaluate((el) => el.getBoundingClientRect().y);
  expect(Math.abs(sizeTop - queueTop)).toBeLessThan(1);

  for (const section of [sent, created]) {
    const date = section.locator("tbody > tr").first().locator(".order-list-date");
    await expect(date).toContainText("2026年10月25日〜");
    await expect(date).toContainText("2026年10月27日");
    const lines = await date.locator(".order-list-date-range > span").evaluateAll((els) => els.map((el) => el.getBoundingClientRect().y));
    expect(lines[1]).toBeGreaterThan(lines[0]);
    await expect(section.locator("tbody > tr").nth(1).locator(".order-list-date")).toHaveText("2026年10月25日〜2026年10月27日");
    await expect(section.locator("tbody > tr").nth(2).locator(".order-list-date")).toHaveText("2026年10月25日〜2026年10月27日");
    await expect(section.locator("tbody > tr").nth(3).locator(".order-list-date")).toHaveText("2026年10月4日");
    await expect(section.locator("tbody > tr").nth(4).locator(".order-list-date")).toHaveText("2026年10月4日");
    const rowColors = await section.locator("tbody > tr").evaluateAll((rows) => rows.slice(0, 2).map((row) => [...row.children].map((td) => getComputedStyle(td).backgroundColor)));
    expect(new Set(rowColors[0]).size).toBe(1);
    expect(new Set(rowColors[1]).size).toBe(1);
    expect(rowColors[0][0]).not.toBe(rowColors[1][0]);
    const frame = await section.locator(".order-list-table > table").evaluate((el) => ({ collapse: getComputedStyle(el).borderCollapse, spacing: getComputedStyle(el).borderSpacing }));
    expect(frame.collapse).toBe("collapse");
    expect(rowColors[0][0]).toBe("rgb(255, 255, 255)");
    expect(rowColors[1][0]).toBe("rgb(247, 247, 247)");
    const boundary = await section.locator("tbody > tr > td").first().evaluate((el) => ({ width: getComputedStyle(el).borderLeftWidth, style: getComputedStyle(el).borderLeftStyle }));
    expect(boundary.width).toBe("0px");


    expect(await section.locator("tbody > tr").first().locator(".order-project-name").evaluate((el) => el.getBoundingClientRect().width)).toBeGreaterThanOrEqual(288);
  }

  const first = sent.locator("tbody > tr").first();
  await expect(first.getByRole("button", { name: "REQ-000", exact: true })).toHaveCount(1);
  await expect(first.locator(".order-reply-recipients li")).toHaveCount(3);
  await expect(first.locator(".order-reply-status")).toHaveText(["受諾", "未回答", "辞退"]);
  await expect(created.locator("tbody > tr").first().locator(".test-data-badge")).toBeVisible();
  await expect(sent.getByText(/【テスト】追加スタッフ/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("grouped-order-lists.png"), fullPage: true });
  const originalTheme = await page.locator("html").getAttribute("data-theme");
  await page.locator("html").evaluate((el) => el.setAttribute("data-theme", "dark"));
  for (const section of [sent, created]) {
    const colors = await section.locator("tbody > tr").evaluateAll((rows) => rows.slice(0, 2).map((row) => getComputedStyle(row.children[0]).backgroundColor));
    expect(colors[0]).not.toBe(colors[1]);
  }
  await page.locator("html").evaluate((el, theme) => { if (theme) el.setAttribute("data-theme", theme); else el.removeAttribute("data-theme"); }, originalTheme);

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
  await page.goto("/masters/workers");
  await page.goto("/operations/order-requests");
  await expect(sent.getByLabel("送信した依頼の表示件数")).toHaveValue("50");
  await expect(created.getByLabel("作成した依頼書の表示件数")).toHaveValue("20");
  await expect(sent.locator("tbody > tr")).toHaveCount(50);
  await expect(created.locator("tbody > tr")).toHaveCount(20);
  await page.reload();
  await expect(sent.getByLabel("送信した依頼の表示件数")).toHaveValue("50");
  await expect(created.getByLabel("作成した依頼書の表示件数")).toHaveValue("20");

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


test("participation popup is wide and lists one person on each line", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const people = ["長谷川 亜香里", "渡邊 健太郎", "坂井 貴博", "伊東 空", "宮本 悠真", "大西 結菜", "小野寺 陽介", "石川 美月"].map((name, i) => ({ worker_id: `w${i}`, name, is_newcomer: i >= 3, is_director: i === 1 }));
  const item = { document_id: "doc", version_id: "version", document_number: "OR-20261024-005A", kind: "test", version_no: 1,
    project_name: "【テスト】10月 20日間の飲食店巡回", categories: ["飲食店巡回"], status: "confirmed", work_date_label: "2026年10月10日～2026年10月29日",
    created_by_name: "担当者", recipient_count: 8, change_documents: [], recipients: people.map((p) => ({ ...p, delivery_id: p.worker_id, worker_name: p.name, ack_status: "acked", send_status: "accepted", version_no: 1 })) };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/reply-groups") || path === "/api/order-requests") return reply({ items: [item], total: 1 });
    if (path.endsWith("/participation-calendar")) return reply({ days: [
      { date: "2026-10-10", events: [{ series_id: "s", ...item, ok: people, changing: [], unanswered: [], unavailable: [] }] },
      { date: "2026-10-11", events: [{ series_id: "s", ...item, ok: people.slice(0, 4), changing: people.slice(4, 6), unanswered: people.slice(6, 7), unavailable: people.slice(7) }] },
    ] });
    return reply({ items: [], total: 0 });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/operations/order-requests");
  await page.locator(".is-created").getByRole("button", { name: "参加人数の確認", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: /参加人数の確認/ });
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate((el) => el.getBoundingClientRect().width)).toBeGreaterThanOrEqual(1000);
  const first = dialog.locator("tbody > tr").first();
  const names = first.getByRole("list", { name: "参加OKの稼働者", exact: true }).getByRole("listitem");
  await expect(names).toHaveCount(8);
  const geometry = await names.evaluateAll((els) => els.map((el) => ({ y: el.getBoundingClientRect().y, clipped: el.scrollWidth > el.clientWidth, text: el.textContent })));
  geometry.forEach((row, index) => {
    expect(row.clipped).toBe(false);
    expect(row.text).not.toContain("、");
    if (index) expect(row.y).toBeGreaterThan(geometry[index - 1].y);
  });
  await expect(first.locator(".pc-summary-count")).toHaveText(["8人", "0人", "0人", "× 0人"]);
  const second = dialog.locator("tbody > tr").nth(1);
  await expect(second.getByRole("list", { name: "参加OKの稼働者", exact: true }).getByRole("listitem")).toHaveCount(4);
  await expect(second.getByRole("list", { name: "変更確認待ちの稼働者", exact: true }).getByRole("listitem")).toHaveCount(2);
  await expect(second.getByRole("list", { name: "未回答の稼働者", exact: true }).getByRole("listitem")).toHaveCount(1);
  await expect(second.getByRole("list", { name: "参加不可の稼働者", exact: true }).getByRole("listitem")).toHaveCount(1);
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("wide-participation-one-person-per-line.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.evaluate((el) => el.getBoundingClientRect().width)).toBeLessThanOrEqual(350);
  expect(await dialog.locator(".participation-summary-table").evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
  await dialog.getByRole("button", { name: "閉じる", exact: true }).click();
  await expect(dialog).toHaveCount(0);
});
