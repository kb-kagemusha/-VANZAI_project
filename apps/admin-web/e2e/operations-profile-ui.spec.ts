import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, options: { companyUpdateFailure?: boolean; workerConflict?: boolean; profileRefreshFailure?: boolean; places?: boolean; workers?: any[]; legacyHourly?: boolean; workerProfile?: any } = {}) {
  const writes: { path: string; body: any }[] = [];
  let staff: any[] = [];
  let updatedWorker = false;
  const worker = { id: "test-worker", name: "試験 太郎", furigana: "しけん たろう", is_active: true, tags: [], profile: options.workerProfile ?? null };
  const workers = options.workers ?? [worker];
  let savedVersion: any;
  let clients: any[] = [{ id: "client-a", name: "内部会社A", postal_code: "1500043", address: "東京都渋谷区道玄坂1-2", notes: "既存の社内メモ", phone: "045-111-9999", contact_name: null, contact_email: null, code: null }, { id: "client-b", name: "内部会社B", phone: "03-222-9999", contact_name: null, contact_email: null, code: null }];
  const contacts: Record<string, any[]> = { "client-a": [{ id: "contact-a1", client_id: "client-a", name: "内部担当A1", phone: "090-1111-9999", is_active: true }, { id: "contact-a2", client_id: "client-a", name: "内部担当A2", phone: "090-2222-9999", is_active: true }], "client-b": [{ id: "contact-b1", client_id: "client-b", name: "内部担当B1", phone: "090-3333-9999", is_active: true }] };
  await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "mock-token"); });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return respond({ id: "mock-admin", username: "mock-admin", display_name: "試験管理者", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-token", refresh_token: "mock-refresh", token_type: "bearer" });
    const method = route.request().method();
    if (path === "/api/clients" && method === "POST") {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      const item = { ...body, id: "client-new" }; clients = [...clients, item];
      contacts[item.id] = body.contacts.map((contact: any, index: number) => ({ ...contact, id: `new-contact-${index}`, client_id: item.id, is_active: true })); return respond(item);
    }
    if (/^\/api\/clients\/[^/]+$/.test(path) && method === "PATCH") {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      if (options.companyUpdateFailure) return respond({ detail: "同じコードのクライアントが既に存在します" }, 409);
      clients = clients.map((item) => item.id === path.split("/")[3] ? { ...item, ...body } : item);
      return respond(clients.find((item) => item.id === path.split("/")[3]));
    }
    if (path === "/api/clients") return respond({ items: clients, total: clients.length, offset: 0, limit: 200 });
    if (/^\/api\/clients\/[^/]+\/staff$/.test(path)) {
      const clientId = path.split("/")[3];
      return respond({ items: contacts[clientId] ?? [], total: contacts[clientId]?.length ?? 0, page: 1, limit: 200 });
    }
    if (/^\/api\/clients\/[^/]+\/phone$/.test(path)) {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      clients = clients.map((item) => item.id === path.split("/")[3] ? { ...item, phone: body.phone } : item);
      return respond(clients.find((item) => item.id === path.split("/")[3]));
    }
    if (path === "/api/workers") {
      const params = new URL(route.request().url()).searchParams;
      const offset = Number(params.get("offset") ?? 0), limit = Number(params.get("limit") ?? 200);
      return respond({ items: workers.slice(offset, offset + limit), total: workers.length, offset, limit });
    }
    if (path === "/api/worker-tags") return respond({ items: [{ code: "commercial_d", label: "商業D" }, { code: "food_d", label: "飲食D" }, { code: "event_small_d", label: "小型イベD" }, { code: "event_medium_d", label: "中型イベD" }, { code: "event_large_d", label: "大型イベD" }] });
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

test("worker editor keeps the original station and saves optional additional stations", async ({ page }) => {
  const writes = await setup(page, { workerProfile: { nearest_station: "新宿駅", station_walk_minutes: 12, additional_stations: [{ nearest_station: "代々木駅", station_walk_minutes: 0 }] } });
  await page.goto("/masters/workers");
  await page.locator("tr").filter({ hasText: "試験 太郎" }).getByRole("button", { name: "編集", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "試験 太郎 を編集", exact: true });
  await expect(dialog.getByLabel("最寄り駅2", { exact: true })).toHaveValue("代々木駅");
  await expect(dialog.getByLabel("最寄り駅2まで徒歩（分）", { exact: true })).toHaveValue("0");
  await dialog.getByRole("button", { name: "＋ 最寄り駅を追加", exact: true }).click();
  await dialog.getByLabel("最寄り駅3", { exact: true }).fill("新宿三丁目駅");
  await dialog.getByLabel("最寄り駅3まで徒歩（分）", { exact: true }).fill("15");
  await dialog.getByRole("button", { name: "最寄り駅2を削除", exact: true }).click();
  await expect(dialog.getByLabel("最寄り駅2", { exact: true })).toHaveValue("新宿三丁目駅");
  await dialog.getByRole("button", { name: "＋ 最寄り駅を追加", exact: true }).click();
  await dialog.getByLabel("最寄り駅3", { exact: true }).fill("南新宿駅");
  await dialog.getByRole("button", { name: "＋ 最寄り駅を追加", exact: true }).click();
  await dialog.getByRole("button", { name: "更新する", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "更新完了" })).toBeVisible();
  expect(writes[0].body.profile.nearest_station).toBe("新宿駅");
  expect(writes[0].body.profile.station_walk_minutes).toBe(12);
  expect(writes[0].body.profile.additional_stations).toEqual([{ nearest_station: "新宿三丁目駅", station_walk_minutes: 15 }, { nearest_station: "南新宿駅", station_walk_minutes: null }]);
});

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

test("master tabs initially show only lists and open additions in a popup with distinct borders", async ({ page }) => {
  await setup(page); await page.goto("/masters/data");
  const tabs = page.getByRole("group", { name: "表示切替", exact: true });
  for (const label of ["稼働者", "下請け", "クライアント", "現場", "案件種別", "役割", "VANZAI担当者"]) {
    await tabs.getByRole("button", { name: label, exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "名称", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "新規追加", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: `${label}の新規追加`, exact: true });
    await expect(dialog.getByLabel("名称", { exact: true })).toBeVisible();
    const field = await dialog.getByLabel("名称", { exact: true }).evaluate((el) => ({ height: el.getBoundingClientRect().height, right: el.getBoundingClientRect().right, labelRight: el.closest("label")!.getBoundingClientRect().right }));
    expect(field.height).toBeGreaterThanOrEqual(44); expect(field.right).toBeLessThanOrEqual(field.labelRight + 1);
    await dialog.getByRole("button", { name: "閉じる", exact: true }).click();
  }
  const colors = await tabs.getByRole("button").evaluateAll((elements) => elements.map((el) => getComputedStyle(el).borderTopColor));
  expect(new Set(colors).size).toBe(7);
});

test("client popup saves company phone and multiple contact phones atomically", async ({ page }) => {
  const writes = await setup(page); await page.goto("/masters/data");
  await page.getByRole("group", { name: "表示切替", exact: true }).getByRole("button", { name: "クライアント", exact: true }).click();
  await page.getByRole("button", { name: "新規追加", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "クライアントの新規追加" });
  await dialog.getByLabel("名称", { exact: true }).fill("新規会社");
  await dialog.getByLabel("会社電話番号", { exact: true }).fill("0451111111");
  await dialog.getByLabel("担当者1の氏名", { exact: true }).fill("担当一");
  await dialog.getByLabel("担当者1の電話番号", { exact: true }).fill("09011111111");
  await dialog.getByLabel("担当者1の役職", { exact: true }).fill("営業部長");
  await dialog.getByLabel("社内メモ", { exact: true }).fill("請求前に電話確認");
  await page.route("https://zipcloud.ibsnet.co.jp/**", (route) => route.fulfill({ json: { status: 200, results: [{ zipcode: "1500043", address1: "東京都", address2: "渋谷区", address3: "道玄坂" }] } }));
  await dialog.getByLabel("郵便番号", { exact: true }).fill("１５０－００４３");
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都渋谷区道玄坂");
  await dialog.getByLabel("住所", { exact: true }).fill("東京都渋谷区道玄坂1-2 試験ビル");
  await dialog.getByRole("button", { name: "担当者を追加", exact: true }).click();
  await dialog.getByLabel("担当者2の氏名", { exact: true }).fill("担当二");
  await dialog.getByLabel("担当者2の電話番号", { exact: true }).fill("09022222222");
  await dialog.getByLabel("担当者2の役職", { exact: true }).fill("課長");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  const addButton = dialog.getByRole("button", { name: "クライアントを追加", exact: true });
  expect((await addButton.boundingBox())!.width).toBeLessThan(210);
  await page.screenshot({ path: "artifacts/client-registration-mobile.png", fullPage: true });
  await addButton.click();
  await expect(dialog).toHaveCount(0);
  expect(writes[0].body.phone).toBe("0451111111");
  expect(writes[0].body.postal_code).toBe("1500043");
  expect(writes[0].body.notes).toBe("請求前に電話確認");
  expect(writes[0].body.contacts).toEqual([{ name: "担当一", role: "営業部長", phone: "09011111111", email: null }, { name: "担当二", role: "課長", phone: "09022222222", email: null }]);
  const row = page.getByRole("row").filter({ hasText: "新規会社" });
  await row.getByRole("button", { name: "担当者管理", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "新規会社の会社電話・担当者管理" }).getByText("課長", { exact: true })).toBeVisible();
  await expect(page.getByText("社内メモ: 請求前に電話確認", { exact: true })).toBeVisible();
});

test("existing company phone updates inside contact management popup", async ({ page }) => {
  const writes = await setup(page); await page.goto("/masters/data");
  await page.getByRole("group", { name: "表示切替", exact: true }).getByRole("button", { name: "クライアント", exact: true }).click();
  await page.getByRole("row").filter({ hasText: "内部会社A" }).getByRole("button", { name: "担当者管理" }).click();
  const dialog = page.getByRole("dialog", { name: "内部会社Aの会社電話・担当者管理" });
  await dialog.getByLabel("会社電話番号", { exact: true }).fill("0459999999");
  await dialog.getByRole("button", { name: "会社電話番号を更新", exact: true }).click();
  await expect(dialog.getByText("会社電話番号を更新しました", { exact: true })).toBeVisible();
  expect(writes[0]).toEqual({ path: "/api/clients/client-a/phone", body: { phone: "0459999999" } });
});

test("order client selection scopes contacts resets stale selection and stays out of public body", async ({ page }) => {
  const writes = await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const company = page.getByRole("combobox", { name: "発注元", exact: true });
  const contact = page.getByRole("combobox", { name: "担当者（発注元）", exact: true });
  await company.selectOption("client-a"); await contact.selectOption("contact-a2");
  await expect(page.getByText(/担当者電話：090-2222-9999/)).toBeVisible();
  await company.selectOption("client-b"); await expect(contact).toHaveValue("");
  await expect(contact.getByRole("option", { name: "内部担当A2", exact: true })).toHaveCount(0);
  await contact.selectOption("contact-b1"); await page.getByLabel(/^期限の案内/).fill("2027-02-20");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].body.internal_source).toEqual({ client_id: "client-b", client_staff_id: "contact-b1" });
  for (const marker of ["内部会社B", "内部担当B1", "090-3333-9999", "internal_source"]) {
    expect(writes[0].body.body).not.toContain(marker); expect(writes[0].body.request_conditions).not.toContain(marker);
  }
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
  await page.getByLabel("稼働日の開始", { exact: true }).fill("2027-03-01");
  await page.getByLabel("稼働日の終了", { exact: true }).fill("2027-03-12");
  await page.getByRole("textbox", { name: "稼働日の補足（全体）", exact: true }).fill("3/11・3/12は予備日");
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
  expect(payload.work_date_label).toBe("2027年3月1日～2027年3月12日");
  expect(JSON.parse(payload.request_conditions).work_period).toEqual({ from: "2027-03-01", to: "2027-03-12" });
  expect(payload.body).toContain("3/11・3/12は予備日");
  expect(payload).not.toHaveProperty("assign_tracker_self"); expect(payload).not.toHaveProperty("tracker_user_id");
  await expect(page.getByLabel("稼働日の終了", { exact: true })).toHaveValue("2027-03-12");
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
  await expect(page.getByRole("heading", { name: "稼働時間の詳細", exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /追跡担当/ })).toHaveCount(0);
  const dates = await page.getByLabel("稼働日の開始", { exact: true }).evaluate((el) => el.closest(".order-field")!.getBoundingClientRect().y);
  const notes = await page.getByRole("textbox", { name: "稼働日の補足（全体）", exact: true }).evaluate((el) => el.closest(".order-field")!.getBoundingClientRect().y);
  expect(Math.abs(dates - notes)).toBeLessThan(2);
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
  await expect(roles.getByRole("checkbox")).toHaveCount(5);
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

test("event director filters include larger qualifications and combine with unrelated roles", async ({ page }) => {
  await setup(page, { workers: [
    { id: "small", name: "小型担当", tags: ["event_small_d"] }, { id: "medium", name: "中型担当", tags: ["event_medium_d"] },
    { id: "large", name: "大型担当", tags: ["event_large_d"] }, { id: "food", name: "飲食担当", tags: ["food_d"] },
  ] });
  await page.goto("/operations/order-requests"); await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  const roles = page.getByRole("group", { name: "付与ロールで絞り込み", exact: true });
  const choices = page.locator(".order-recipient-list");
  await expect(roles.getByText(/小型を選ぶと小型・中型・大型/)).toBeVisible();
  await roles.getByRole("checkbox", { name: "小型イベD", exact: true }).check();
  await expect(choices.getByRole("checkbox")).toHaveCount(3);
  await choices.getByRole("checkbox", { name: /小型担当/ }).check();
  await roles.getByRole("checkbox", { name: "小型イベD", exact: true }).uncheck();
  await roles.getByRole("checkbox", { name: "中型イベD", exact: true }).check();
  await expect(choices.getByRole("checkbox")).toHaveCount(2);
  await expect(choices.getByRole("checkbox", { name: /小型担当/ })).toHaveCount(0);
  await roles.getByRole("checkbox", { name: "中型イベD", exact: true }).uncheck();
  await roles.getByRole("checkbox", { name: "大型イベD", exact: true }).check();
  await expect(choices.getByRole("checkbox")).toHaveCount(1);
  await expect(choices.getByRole("checkbox", { name: /大型担当/ })).toBeVisible();
  await roles.getByRole("checkbox", { name: "飲食D", exact: true }).check();
  await expect(choices.getByRole("checkbox")).toHaveCount(2);
  await expect(page.locator(".order-recipient-picks").getByText("小型担当")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
});


test("client postal lookup preserves typed addresses and offers multiple matches", async ({ page }) => {
  await setup(page); await page.goto("/masters/data");
  await page.getByRole("group", { name: "表示切替", exact: true }).getByRole("button", { name: "クライアント", exact: true }).click();
  await page.getByRole("button", { name: "新規追加", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "クライアントの新規追加" });
  await page.route("https://zipcloud.ibsnet.co.jp/**", (route) => {
    const postal = new URL(route.request().url()).searchParams.get("zipcode");
    return route.fulfill({ json: { status: 200, results: postal === "1111111" ? [{ zipcode: postal, address1: "東京都", address2: "試験区", address3: "一丁目" }] : postal === "2222222" ? [{ zipcode: postal, address1: "東京都", address2: "試験区", address3: "二丁目" }, { zipcode: postal, address1: "東京都", address2: "試験区", address3: "三丁目" }] : null } });
  });
  await dialog.getByLabel("住所", { exact: true }).fill("入力済み住所・建物名");
  await dialog.getByLabel("郵便番号", { exact: true }).fill("1111111");
  await expect(dialog.getByRole("status")).toContainText("取得しました");
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("入力済み住所・建物名");
  await dialog.getByLabel("郵便番号", { exact: true }).fill("2222222");
  await dialog.getByRole("button", { name: "東京都試験区三丁目", exact: true }).click();
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都試験区三丁目");
  await dialog.getByLabel("郵便番号", { exact: true }).fill("3333333");
  await expect(dialog.getByRole("status")).toContainText("見つかりませんでした");
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都試験区三丁目");
});


test("client company can be edited from its master row and reopened with saved values", async ({ page }) => {
  const writes = await setup(page); await page.goto("/masters/data");
  await page.getByRole("group", { name: "表示切替", exact: true }).getByRole("button", { name: "クライアント", exact: true }).click();
  await page.getByRole("row").filter({ hasText: "内部会社A" }).getByRole("button", { name: "編集", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "内部会社Aの企業情報を編集", exact: true });
  await expect(dialog.getByLabel("企業名", { exact: true })).toHaveValue("内部会社A");
  await expect(dialog.getByLabel("郵便番号", { exact: true })).toHaveValue("1500043");
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都渋谷区道玄坂1-2");
  await expect(dialog.getByLabel("社内メモ", { exact: true })).toHaveValue("既存の社内メモ");
  await dialog.getByLabel("企業名", { exact: true }).fill("修正会社A");
  await dialog.getByLabel("社内メモ", { exact: true }).fill("変更した社内メモ");
  await page.route("https://zipcloud.ibsnet.co.jp/**", (route) => route.fulfill({ json: { status: 200, results: [{ zipcode: "1000001", address1: "東京都", address2: "千代田区", address3: "千代田" }] } }));
  await dialog.getByLabel("郵便番号", { exact: true }).fill("１００－０００１");
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都渋谷区道玄坂1-2");
  await dialog.getByRole("button", { name: "東京都千代田区千代田", exact: true }).click();
  await dialog.getByLabel("住所", { exact: true }).fill("東京都千代田区千代田1-1");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await dialog.getByRole("button", { name: "企業情報を更新", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "修正会社Aの企業情報を編集", exact: true });
  await expect(dialog.getByText("企業情報を更新しました", { exact: true })).toBeVisible();
  expect(writes[0]).toEqual({ path: "/api/clients/client-a", body: { name: "修正会社A", postal_code: "1000001", address: "東京都千代田区千代田1-1", notes: "変更した社内メモ" } });
  await dialog.getByRole("button", { name: "閉じる", exact: true }).last().click();
  await page.getByRole("row").filter({ hasText: "修正会社A" }).getByRole("button", { name: "編集", exact: true }).click();
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都千代田区千代田1-1");
  await expect(dialog.getByLabel("会社電話番号", { exact: true })).toHaveValue("045-111-9999");
  await dialog.getByRole("button", { name: "企業情報を更新", exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: "artifacts/client-company-editor-mobile.png" });
});

test("company update errors keep input and cancel sends no update", async ({ page }) => {
  const writes = await setup(page, { companyUpdateFailure: true }); await page.goto("/masters/data");
  await page.getByRole("group", { name: "表示切替", exact: true }).getByRole("button", { name: "クライアント", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "内部会社A" });
  await row.getByRole("button", { name: "編集", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "内部会社Aの企業情報を編集", exact: true });
  await dialog.getByLabel("企業名", { exact: true }).fill("保存しない名前");
  await dialog.getByRole("button", { name: "閉じる", exact: true }).last().click();
  expect(writes).toEqual([]);
  await row.getByRole("button", { name: "編集", exact: true }).click();
  await expect(dialog.getByLabel("企業名", { exact: true })).toHaveValue("内部会社A");
  await dialog.getByLabel("コード", { exact: true }).fill("重複コード");
  await dialog.getByRole("button", { name: "企業情報を更新", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("同じコード");
  await expect(dialog.getByLabel("コード", { exact: true })).toHaveValue("重複コード");
  await expect(dialog.getByLabel("住所", { exact: true })).toHaveValue("東京都渋谷区道玄坂1-2");
});
