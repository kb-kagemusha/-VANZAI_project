import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, options: { workerConflict?: boolean; profileRefreshFailure?: boolean; places?: boolean; workers?: any[]; legacyHourly?: boolean } = {}) {
  const writes: { path: string; body: any }[] = [];
  let staff: any[] = [];
  let updatedWorker = false;
  const worker = { id: "test-worker", name: "試験 太郎", furigana: "しけん たろう", is_active: true, tags: [], profile: null };
  const workers = options.workers ?? [worker];
  let savedVersion: any;
  await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "mock-token"); });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return respond({ id: "mock-admin", username: "mock-admin", display_name: "試験管理者", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-token", refresh_token: "mock-refresh", token_type: "bearer" });
    const method = route.request().method();
    if (path === "/api/workers") {
      const params = new URL(route.request().url()).searchParams;
      const offset = Number(params.get("offset") ?? 0), limit = Number(params.get("limit") ?? 200);
      return respond({ items: workers.slice(offset, offset + limit), total: workers.length, offset, limit });
    }
    if (path === "/api/worker-tags") return respond({ items: [{ code: "commercial_d", label: "商業D" }, { code: "food_d", label: "飲食D" }] });
    if (path === "/api/workers/test-worker/edit-guard") {
      if (updatedWorker && options.profileRefreshFailure) return respond({ detail: "読み込み失敗" }, 500);
      return respond({ worker, edit_guard: updatedWorker ? "fresh-guard" : "initial-guard" });
    }
    if (path === "/api/workers/test-worker" && method === "PUT") {
      writes.push({ path, body: route.request().postDataJSON() });
      if (options.workerConflict) return respond({ detail: "他の担当者が更新しています" }, 409);
      updatedWorker = true; return respond(worker);
    }
    if (path === "/api/operator-staff" && method === "POST") {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      staff = [{ ...body, id: "operator1", profile_revision: 1, line_linked: false, line_display_name: null, line_linked_at: null }]; return respond(staff[0], 201);
    }
    if (path === "/api/operator-staff") return respond({ items: staff, total: staff.length, offset: 0, limit: 30 });
    if (path === "/api/operator-staff/operator1/line-code") return respond({ code: "OPS-ABCDEFGH", expires_at: "2099-01-01T01:00:00Z", instruction: "本人が公式LINEへコードを送信" });
    if (path === "/api/places/status") return respond({ configured: options.places ?? false });
    if (path === "/api/places/search") return respond({ items: [{ place_id: "ChIJ-test", name: "横浜赤レンガ倉庫 イベント広場", address: "Google検索結果の住所", attributions: [] }] });
    if (path === "/api/order-requests" && method === "POST") {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      savedVersion = { ...body, document_id: "doc", document_number: "OR-TEST-001A", id: "version1", version_no: 1, status: "draft", draft_worker_ids: body.worker_ids, deliveries: [], notes: [], change_documents: [], has_pdf: false, line_send_available: false, created_at: "2026-10-13T01:00:00Z" };
      if (options.legacyHourly) {
        const stored = JSON.parse(savedVersion.request_conditions);
        stored.schedule.rate_groups[0].unit = "hour"; stored.schedule.rate_groups[0].amount = "1200";
        savedVersion.request_conditions = JSON.stringify(stored);
      }
      return respond(savedVersion);
    }
    if (path === "/api/order-requests/versions/version1" && method === "PATCH") {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      savedVersion = { ...savedVersion, ...body, draft_worker_ids: body.worker_ids }; return respond(savedVersion);
    }
    if (path === "/api/order-requests/versions/version1") return respond(savedVersion);
    return respond({ items: [], total: 0, offset: 0, limit: 30, line_send_available: false });
  });
  return writes;
}

test("worker successful update shows success popup and keeps editor open", async ({ page }) => {
  const writes = await setup(page);
  await page.goto("/masters/workers");
  await page.locator("tr").filter({ hasText: "試験 太郎" }).getByRole("button", { name: "編集", exact: true }).click();
  await page.getByRole("button", { name: "更新する", exact: true }).click();
  const popup = page.getByRole("dialog", { name: "更新完了" });
  await expect(popup.getByText("情報を更新しました", { exact: true })).toBeVisible();
  expect(writes[0].body.edit_guard).toBe("initial-guard");
  await popup.getByRole("button", { name: "OK" }).click();
  await expect(page.getByRole("button", { name: "更新する", exact: true })).toBeVisible();
});

test("conflicting worker update does not show success popup", async ({ page }) => {
  await setup(page, { workerConflict: true }); await page.goto("/masters/workers");
  await page.locator("tr").filter({ hasText: "試験 太郎" }).getByRole("button", { name: "編集", exact: true }).click();
  await page.getByRole("button", { name: "更新する", exact: true }).click();
  await expect(page.getByText("他の担当者が更新しています")).toBeVisible();
  await expect(page.getByRole("dialog", { name: "更新完了" })).toHaveCount(0);
});

test("successful save with failed refresh still reports saved and disables stale resave", async ({ page }) => {
  await setup(page, { profileRefreshFailure: true }); await page.goto("/masters/workers");
  await page.locator("tr").filter({ hasText: "試験 太郎" }).getByRole("button", { name: "編集", exact: true }).click();
  await page.getByRole("button", { name: "更新する", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "更新完了" })).toBeVisible();
  await page.getByRole("dialog", { name: "更新完了" }).getByRole("button", { name: "OK" }).click();
  await expect(page.getByText(/情報は保存済みですが/)).toBeVisible();
  await expect(page.getByRole("button", { name: "更新する", exact: true })).toBeDisabled();
});

test("daily and ranged work preserve matching prices and expense notes in saved document", async ({ page }) => {
  const writes = await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByLabel("稼働日の詳細1の開始日").fill("2027-03-01");
  const first = page.getByRole("group", { name: "稼働日の詳細 1", exact: true });
  await first.getByLabel("開始時間").fill("08:00"); await first.getByLabel("終了時間").fill("17:00");
  await first.getByLabel("稼働日の備考").fill("初日準備");
  await page.getByRole("button", { name: "稼働日・期間を追加" }).click();
  await page.getByRole("group", { name: "稼働日の詳細2の日付の設定", exact: true }).getByRole("button", { name: "複数日の期間", exact: true }).click();
  await page.getByLabel("稼働日の詳細2の開始日").fill("2027-03-02"); await page.getByLabel("稼働日の詳細2の終了日").fill("2027-03-10");
  const second = page.getByRole("group", { name: "稼働日の詳細 2", exact: true });
  await second.getByLabel("開始時間").fill("09:00"); await second.getByLabel("終了時間").fill("17:00");
  await expect(page.getByRole("checkbox", { name: "稼働日の設定で単価設定する" })).toBeChecked();
  const rates = page.locator("fieldset").filter({ has: page.getByLabel("単価（円・税抜）") });
  await rates.nth(0).getByLabel("単価（円・税抜）").fill("20500");
  await rates.nth(1).getByLabel("単価（円・税抜）").fill("19500");
  await expect(rates.nth(0).getByLabel("昼食代：込み")).toBeChecked(); await expect(rates.nth(0).getByLabel("交通費：込み")).toBeChecked();
  await rates.nth(1).getByLabel("交通費：込み").uncheck(); await rates.nth(1).getByLabel("交通費の備考").fill("実費上限1,000円");
  await first.screenshot({ path: "../../artifacts/order-date-groups.png" });
  await page.getByLabel("所在地の登録住所").fill("主催者確認住所");
  await page.getByLabel("Google Mapsの共有URL").fill("https://maps.app.goo.gl/TEST-location");
  await page.getByLabel(/^期限の案内/).fill("2027-02-20");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect(page.getByText("下書きを保存しました。確定するまで送付は始まりません。")).toBeVisible();
  const payload = writes.find((w) => w.path === "/api/order-requests")!.body;
  const schedule = JSON.parse(payload.request_conditions).schedule;
  expect(schedule.rate_groups.every((rate: any) => rate.unit === "day")).toBe(true);
  expect(schedule.work_groups).toHaveLength(2); expect(schedule.rate_groups).toHaveLength(2);
  expect(schedule.rate_groups[1].from).toBe("2027-03-02"); expect(schedule.rate_groups[1].to).toBe("2027-03-10");
  expect(payload.body).toContain("¥20,500"); expect(payload.body).toContain("交通費：別途（実費上限1,000円）"); expect(payload.body).toContain("主催者確認住所");
  expect(JSON.parse(payload.request_conditions).maps_url).toBe("https://maps.app.goo.gl/TEST-location");
  expect(payload.body).toContain("https://maps.app.goo.gl/TEST-location");
});

test("venue and general date notes match project half width and rates only offer daily pay", async ({ page }) => {
  await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const project = await page.getByRole("textbox", { name: "案件名", exact: true }).boundingBox();
  for (const name of ["稼働場所", "稼働日の補足（全体）"]) {
    const box = await page.getByRole("textbox", { name, exact: true }).boundingBox();
    expect(Math.abs(box!.width - project!.width)).toBeLessThan(2);
  }
  const rate = page.locator("fieldset.order-rate-row");
  await expect(rate.getByText("単位：日給", { exact: true })).toBeVisible();
  await expect(rate.getByRole("button", { name: "時給", exact: true })).toHaveCount(0);
  await expect(rate.getByRole("combobox")).toHaveCount(0);
});

test("legacy hourly price stays unchanged until explicit daily conversion and new amount entry", async ({ page }) => {
  const writes = await setup(page, { legacyHourly: true }); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByLabel(/^期限の案内/).fill("2027-02-20");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  const rate = page.locator("fieldset.order-rate-row");
  await expect(rate.getByText("単位：保存済みの旧時給", { exact: true })).toBeVisible();
  await expect(rate.getByLabel("単価（円・税抜）")).toHaveValue("1200");
  await expect(rate.getByLabel("単価（円・税抜）")).toHaveAttribute("readonly", "");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect.poll(() => writes.length).toBe(2);
  expect(JSON.parse(writes[1].body.request_conditions).schedule.rate_groups[0]).toMatchObject({ unit: "hour", amount: "1200" });
  await rate.getByRole("button", { name: "日給へ変更", exact: true }).click();
  await page.getByRole("dialog", { name: "日給へ変更" }).getByRole("button", { name: "キャンセル" }).click();
  await expect(rate.getByLabel("単価（円・税抜）")).toHaveValue("1200");
  await rate.getByRole("button", { name: "日給へ変更", exact: true }).click();
  await page.getByRole("dialog", { name: "日給へ変更" }).getByRole("button", { name: "日給を入力する" }).click();
  await expect(rate.getByLabel("単価（円・税抜）")).toHaveValue("");
  await rate.getByLabel("単価（円・税抜）").fill("18000");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect.poll(() => writes.length).toBe(3);
  expect(JSON.parse(writes[2].body.request_conditions).schedule.rate_groups[0]).toMatchObject({ unit: "day", amount: "18000" });
});

test("date conditions and operator editor fit a mobile screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByRole("group", { name: "稼働日の詳細 1", exact: true }).scrollIntoViewIfNeeded();
  expect(await page.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.goto("/masters/operator-staff"); await page.getByRole("button", { name: "運営スタッフを登録" }).click();
  expect(await page.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.getByRole("dialog", { name: "運営スタッフ登録" }).getByRole("button", { name: "閉じる" }).click();
  await expect(page.getByRole("dialog", { name: "運営スタッフ登録" })).toHaveCount(0);
});

test("Google place selection stores ID while address remains user supplied and venue edits clear stale ID", async ({ page }) => {
  await setup(page, { places: true }); await page.goto("/operations/order-requests"); await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByRole("textbox", { name: "稼働場所", exact: true }).fill("横浜赤レンガ倉庫 イベント広場");
  await page.getByText("APIによる会場検索", { exact: true }).click();
  await page.getByRole("button", { name: "所在地を検索" }).click();
  await expect(page.getByText("Google検索結果の住所")).toBeVisible();
  await page.getByRole("button", { name: "この地点を選択" }).click();
  await expect(page.getByText(/Google Mapsの地点を紐付け済み/)).toBeVisible();
  await expect(page.getByLabel("所在地の登録住所")).toHaveValue("");
  await page.getByRole("textbox", { name: "稼働場所", exact: true }).fill("別会場");
  await expect(page.getByText(/Google Mapsの地点を紐付け済み/)).toHaveCount(0);
});

test("operator registration popup saves all fields and issues separate LINE code", async ({ page }) => {
  const writes = await setup(page); await page.goto("/masters/operator-staff");
  await expect(page.getByRole("link", { name: /運営スタッフ登録・一覧/ })).toBeVisible();
  await page.getByRole("button", { name: "運営スタッフを登録" }).click();
  const dialog = page.getByRole("dialog", { name: "運営スタッフ登録" });
  await dialog.getByLabel("氏名", { exact: true }).fill("運営テスト"); await dialog.getByLabel("電話番号", { exact: true }).fill("09011112222");
  await dialog.getByLabel("運転可否").selectOption("true"); await dialog.getByLabel("喫煙可否").selectOption("false");
  await dialog.getByLabel("緊急連絡先の氏名").fill("家族"); await dialog.getByLabel("緊急連絡先の電話番号").fill("09033334444");
  await dialog.getByLabel("現場管理", { exact: true }).check(); await dialog.getByLabel("基礎管理", { exact: true }).check();
  await dialog.getByRole("button", { name: "登録", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "保存完了" }).getByText("運営スタッフを登録しました")).toBeVisible();
  await page.getByRole("dialog", { name: "保存完了" }).getByRole("button", { name: "OK" }).click();
  expect(writes[0].body.management_roles).toEqual(["現場管理", "基礎管理"]); expect(writes[0].body.can_drive).toBe(true);
  await page.getByRole("button", { name: "LINE紐付けコードを発行" }).click(); await expect(page.getByText("OPS-ABCDEFGH")).toBeVisible();
  await page.screenshot({ path: "../../artifacts/operator-staff-dialog.png", fullPage: false });
});

test("date buttons switch visible fields, retain the range, and show overnight confirmation only when needed", async ({ page }) => {
  await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const detail = page.getByRole("group", { name: "稼働日の詳細 1", exact: true });
  const mode = detail.getByRole("group", { name: "稼働日の詳細1の日付の設定", exact: true });
  await expect(detail.getByRole("combobox")).toHaveCount(0);
  await expect(detail.getByLabel("集合時間（任意）")).toHaveCount(0);
  await expect(mode.getByRole("button", { name: "1日ごと", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("稼働日の詳細1の開始日").fill("2027-03-01");
  await mode.getByRole("button", { name: "複数日の期間", exact: true }).click();
  await page.getByLabel("稼働日の詳細1の終了日").fill("2027-03-10");
  await mode.getByRole("button", { name: "1日ごと", exact: true }).click();
  await expect(page.getByLabel("稼働日の詳細1の終了日")).toHaveCount(0);
  await mode.getByRole("button", { name: "複数日の期間", exact: true }).click();
  await expect(page.getByLabel("稼働日の詳細1の終了日")).toHaveValue("2027-03-10");
  await detail.getByLabel("開始時間").fill("08:00"); await detail.getByLabel("終了時間").fill("17:00");
  await expect(detail.getByLabel("日をまたいで翌日に終了する")).toHaveCount(0);
  await detail.getByLabel("開始時間").fill("22:00"); await detail.getByLabel("終了時間").fill("06:00");
  await expect(detail.getByLabel("日をまたいで翌日に終了する")).not.toBeChecked();
  await expect(detail.getByText(/22:00開始・翌朝6:00終了/)).toBeVisible();
  await detail.getByLabel("日をまたいで翌日に終了する").check();
  await expect(detail.getByLabel("日をまたいで翌日に終了する")).toBeChecked();
});

test("lunch and transport notes share one row on desktop and mobile", async ({ page }) => {
  await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const rate = page.locator("fieldset.order-rate-row");
  await rate.getByLabel("昼食代：込み").uncheck(); await rate.getByLabel("交通費：込み").uncheck();
  await rate.getByLabel("昼食代の備考").fill("500円別途支給"); await rate.getByLabel("交通費の備考").fill("実費精算");
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const lunch = await rate.getByLabel("昼食代の備考").evaluate((el) => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width }; });
    const transport = await rate.getByLabel("交通費の備考").evaluate((el) => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y }; });
    expect(Math.abs(lunch.y - transport.y)).toBeLessThan(2);
    expect(transport.x).toBeGreaterThan(lunch.x + lunch.width);
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await rate.screenshot({ path: "../../artifacts/order-expense-columns.png" });
});

test("multiple recipient roles use union and name filtering preserves selected recipients", async ({ page }) => {
  await setup(page, { workers: [{ id: "one", name: "商業担当", tags: ["commercial_d"] }, { id: "two", name: "飲食担当", tags: ["food_d"] }, { id: "both", name: "両方担当", tags: ["commercial_d", "food_d"] }, { id: "none", name: "未付与", tags: [] }] });
  await page.goto("/operations/order-requests"); await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const choices = page.locator(".order-recipient-list");
  const roles = page.getByRole("group", { name: "付与ロールで絞り込み", exact: true });
  await expect(roles.getByRole("checkbox")).toHaveCount(2);
  await roles.getByRole("checkbox", { name: "商業D", exact: true }).check();
  await expect(choices.getByRole("checkbox")).toHaveCount(2);
  await choices.getByRole("checkbox", { name: /商業担当/ }).check();
  await roles.getByRole("checkbox", { name: "飲食D", exact: true }).check();
  await expect(choices.getByRole("checkbox")).toHaveCount(3);
  await expect(choices.getByRole("checkbox", { name: /飲食担当/ })).toBeVisible();
  await expect(page.locator(".order-recipient-picks").getByText("商業担当")).toBeVisible();
  await page.getByLabel("氏名・付与ロールで検索").fill("飲食担当");
  await expect(choices.getByRole("checkbox")).toHaveCount(1);
  await page.getByLabel("氏名・付与ロールで検索").fill("");
  await roles.getByRole("checkbox", { name: "飲食D", exact: true }).uncheck();
  await expect(choices.getByRole("checkbox")).toHaveCount(2);
  await roles.getByRole("button", { name: "ロールの絞り込みを解除" }).click();
  await expect(choices.getByRole("checkbox")).toHaveCount(4);
  await expect(choices.getByRole("checkbox", { name: /商業担当/ })).toBeChecked();
});

test("40 recipients can be selected and the 41st is blocked until a selection is cleared", async ({ page }) => {
  const workers = Array.from({ length: 41 }, (_, i) => ({ id: `worker-${i}`, name: `送付先${String(i).padStart(2, "0")}`, tags: [] }));
  await setup(page, { workers }); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const choices = page.locator(".order-recipient-list");
  for (let i = 0; i < 40; i++) await choices.getByRole("checkbox", { name: `送付先${String(i).padStart(2, "0")}`, exact: true }).check();
  await expect(page.locator(".order-count")).toHaveText("40 / 40");
  await expect(choices.getByRole("checkbox", { name: "送付先40", exact: true })).toBeDisabled();
  await choices.getByRole("checkbox", { name: "送付先00", exact: true }).uncheck();
  await choices.getByRole("checkbox", { name: "送付先40", exact: true }).check();
  await expect(page.locator(".order-count")).toHaveText("40 / 40");
});

test("role filtering also finds recipients after the first API page", async ({ page }) => {
  const workers = Array.from({ length: 201 }, (_, i) => ({ id: `worker-${i}`, name: `後方確認${String(i).padStart(3, "0")}`, tags: i === 200 ? ["commercial_d"] : ["food_d"] }));
  await setup(page, { workers }); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByRole("group", { name: "付与ロールで絞り込み", exact: true }).getByRole("checkbox", { name: "商業D", exact: true }).check();
  await expect(page.locator(".order-recipient-list").getByRole("checkbox")).toHaveCount(1);
  await expect(page.locator(".order-recipient-list").getByRole("checkbox", { name: /後方確認200/ })).toBeVisible();
});
