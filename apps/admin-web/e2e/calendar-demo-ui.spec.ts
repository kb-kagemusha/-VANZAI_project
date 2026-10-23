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
    const include = url.searchParams.get("test_only") === "true";
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
  await page.getByRole("button", { name: "テストのみ", exact: true }).click();
  await expect(page.locator(".ov-event-box.ov-c3")).toContainText("フェステスト");
  await expect(page.locator(".ov-event-box.ov-c6")).toContainText("研修テスト");
  await expect(page.locator(".overview-row-name .test-data-badge")).toHaveCount(0);
  for (const name of ["稼働者ごと", "参加カレンダー", "出勤可能日"]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(page.getByRole("button", { name: "テストのみ", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".ov-c3").filter({ hasText: "フェステスト" }).first()).toBeVisible();
  }
  await page.getByRole("button", { name: "正式のみ", exact: true }).click();
  await expect(page.getByText("フェステスト", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "テストのみ", exact: true }).click();
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

test("event outlines stay rectangular and worker runs span consecutive dates without bridging NG days", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const person = (id: string) => ({ worker_id: id, name: `稼働者${id}` });
  const event = (id: string, ok: string[], unavailable: string[] = []) => ({ series_id: id, version_id: id, document_number: id,
    project_name: id === "a" ? "連日フェス" : "連日巡回", categories: [id === "a" ? "フェス系" : "飲食店巡回"], is_test: true,
    ok: ok.map(person), changing: [], unanswered: [], unavailable: unavailable.map(person) });
  const days = [
    { date: "2026-10-10", events: [event("a", ["1", "2"])] },
    { date: "2026-10-11", events: [event("a", ["2", "3", "4", "5", "6"], ["1"]), event("b", ["1"])] },
    { date: "2026-10-12", events: [event("a", ["1", "2"]), event("b", ["1"])] },
    { date: "2026-10-14", events: [event("a", ["1", "2"])] },
  ];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/participation-calendar")) return reply({ days, workers: ["1", "2"].map((id) => ({ ...person(id), line_linked: false })) });
    return reply({ items: [], total: 0, missing_count: 0 });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/operations/calendar?view=event&month=2026-10&test=1");
  const run = page.locator('.ov-event-run[data-series-id="a"]').first();
  await expect(run.locator(".ov-event-box")).toHaveCount(3);
  const rects = await run.locator(".ov-event-box").evaluateAll((nodes) => nodes.map((node) => { const r = node.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; }));
  expect(Math.max(...rects.map((r) => r.bottom)) - Math.min(...rects.map((r) => r.bottom))).toBeLessThan(1);
  expect(Math.max(...rects.map((r) => r.top)) - Math.min(...rects.map((r) => r.top))).toBeLessThan(1);
  await expect(run.locator(".is-unavailable")).toContainText("× 稼働者1");
  await run.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("event-rectangle.png"), fullPage: true });
  await page.getByRole("tab", { name: "稼働者ごと", exact: true }).click();
  const w2 = page.locator('tr[data-worker-id="2"]');
  await expect(w2.locator('.ov-worker-run[data-series-id="a"][data-days="3"]')).toHaveCount(1);
  await expect(w2.locator('.ov-worker-run[data-series-id="a"]')).toHaveCount(2); // 13日の空白で分割
  const w1 = page.locator('tr[data-worker-id="1"]');
  await expect(w1.locator('.ov-worker-run[data-series-id="a"]')).toHaveCount(4); // NG日を跨がない
  await expect(w1.locator('.ov-worker-run[data-series-id="b"][data-days="2"]')).toHaveCount(1);
  await expect(w1.locator('.ov-worker-run.is-unavailable')).toContainText("11日 × 参加不可");
  await w1.locator('.ov-worker-run[data-series-id="b"]').scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("worker-continuous.png"), fullPage: true });
});

test("NG name fits the wider day column and undecided is Japanese", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const people = Array.from({ length: 8 }, (_, i) => ({ worker_id: `w${i}`, is_newcomer: i === 0, is_director: i === 0, name: i === 0 ? "長谷川 亜香里" : i === 1 ? "渡邊 健太郎" : `稼働者${i}` }));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/participation-calendar")) return reply({ workers: people.map((p) => ({ ...p, line_linked: false })), days: [
      { date: "2026-10-01", events: [{ series_id: "s", version_id: "v", document_number: "D", project_name: "受付", categories: ["商業施設/たばこ屋"], ok: people, changing: [], unanswered: [], unavailable: [] }] },
      { date: "2026-10-02", events: [{ series_id: "s", version_id: "v", document_number: "D", project_name: "受付", categories: ["商業施設/たばこ屋"], ok: people.slice(1, 5), changing: [], unanswered: [], unavailable: [people[0], ...people.slice(5)] }] },
    ] });
    if (path.endsWith("/availability-calendar")) return reply({ workers: [{ id: "w0", name: "長谷川 亜香里", is_newcomer: true, is_director: true, is_active: true, tags: [], days: { "2026-10-01": { availability_status: "undecided", assignments: [], order_events: [] } } }] });
    return reply({ items: [], total: 0, missing_count: 0 });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/operations/calendar?view=event&month=2026-10&test=1");
  const refused = page.locator(".ov-event-box .ov-person.is-unavailable").first();
  await expect(refused).toHaveText("× 長谷川 亜香里🔰D");
  expect(await refused.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  expect(await page.locator(".overview-head-day").first().evaluate((el) => el.getBoundingClientRect().width)).toBeGreaterThanOrEqual(160);
  await expect(page.locator(".ov-event-box").first()).toContainText("参加OK 8人");
  await expect(page.locator(".ov-event-box").nth(1)).toContainText("参加OK 4人");
  await expect(refused.getByRole("img", { name: "新人（稼働開始日から3か月）" })).toBeVisible();
  await expect(refused.getByRole("img", { name: "ディレクター可能", exact: true })).toBeVisible();
  const boxes = await page.locator(".ov-event-box").evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
  expect(Math.abs(boxes[0] - boxes[1])).toBeLessThan(1);
  await page.screenshot({ path: testInfo.outputPath("eight-to-four-newcomer.png"), fullPage: true });
  await page.getByRole("tab", { name: "稼働者ごと", exact: true }).click();
  await expect(page.locator('tr[data-worker-id="w0"] th').getByRole("img", { name: "新人（稼働開始日から3か月）" })).toBeVisible();
  await page.getByRole("tab", { name: "参加カレンダー", exact: true }).click();
  await page.locator(".pc-day").filter({ hasText: "受付" }).first().click();
  await expect(page.locator(".pc-detail-event").getByRole("img", { name: "新人（稼働開始日から3か月）" })).toBeVisible();
  await page.getByRole("tab", { name: "出勤可能日", exact: true }).click();
  await expect(page.getByText("未定", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: "新人（稼働開始日から3か月）" })).toBeVisible();
  await expect(page.getByText("undecided", { exact: true })).toHaveCount(0);
});


test("director checkbox is available and independent of event-size tags", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const worker = { id: "w", name: "監督 担当", is_active: true, tags: ["director", "event_large_d"], is_director: true, is_newcomer: false, profile: {} };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const reply = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/worker-tags")) return reply({ items: [{ code: "director", label: "ディレクター可能", description: "現場の監督ができる" }, { code: "event_large_d", label: "大型イベD", description: "大型イベントの現場" }] });
    if (path.endsWith("/workers/w/edit-guard")) return reply({ worker, edit_guard: "guard" });
    if (path.endsWith("/workers")) return reply({ items: [worker], total: 1 });
    return reply({ items: [], total: 0 });
  });
  await page.goto("/masters/workers");
  await expect(page.getByRole("img", { name: "ディレクター可能", exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: "新人（稼働開始日から3か月）" })).toHaveCount(0);
  await page.getByRole("button", { name: "編集", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "監督 担当 を編集" });
  const director = dialog.getByRole("checkbox", { name: "ディレクター可能 現場の監督ができる" });
  const large = dialog.getByRole("checkbox", { name: "大型イベD 大型イベントの現場" });
  await expect(director).toBeChecked();
  await expect(large).toBeChecked();
  await director.uncheck();
  await expect(director).not.toBeChecked();
  await expect(large).toBeChecked();
  await director.check();
  await expect(director).toBeChecked();
});
