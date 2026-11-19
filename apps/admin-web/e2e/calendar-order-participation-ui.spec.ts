import { expect, test, type Page } from "@playwright/test";

test.use({ viewport: { width: 1440, height: 900 } });

const schedule = {
  version: 1, rates_follow_work: true,
  work_groups: [{ id: "work", date_mode: "range", from: "2026-10-29", to: "2026-11-04", start_time: "09:00", end_time: "17:00", end_next_day: false, gathering_time: "", notes: "", excluded_dates: ["2026-10-30"] }],
  rate_groups: [{ id: "rate", work_group_id: "work", date_mode: "range", from: "2026-10-29", to: "2026-11-04", unit: "day", amount: "10000", lunch_included: true, transport_included: true, lunch_note: "", transport_note: "", notes: "" }],
};
const version = {
  id: "version-1", document_id: "document-1", document_number: "ORD-2026-001", version_no: 1, kind: "formal", status: "draft",
  change_documents: [], work_date_label: "10月29日〜11月4日", site_name: "会場", site_address: "", contact_name: "なし", contact_desk: "",
  request_conditions: JSON.stringify({ format: "additional-request-v1", project_name: "確認用イベント", categories: ["フェス系"], schedule }),
  body: "【案件依頼】\n確認用イベント\n■集合場所\n会場の受付", draft_worker_ids: ["worker-1"], draft_recipient_absences: {},
  follow_up_due_on: "2026-10-28", follow_up_due_time: "21:00", deliveries: [], notes: [], has_pdf: false, line_send_available: true,
};

async function adminMocks(page: Page) {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const writes: Array<{ path: string; body: any }> = [];
  let template: any = null;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const method = route.request().method();
    const respond = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return respond({ id: "admin", username: "admin", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "test-token", token_type: "bearer" });
    if (path.endsWith("/participation-calendar")) return respond({
      workers: Array.from({ length: 45 }, (_, i) => ({ worker_id: `worker-${i}`, name: `稼働者${i}`, line_linked: true })),
      days: [{ date: "2026-10-29", events: [{ series_id: "series-1", version_id: version.id, document_number: version.document_number, project_name: "確認用イベント", site_name: "表示不要な集合場所", ok: [{ worker_id: "worker-1", name: "稼働者1" }], changing: [], unanswered: [] }] }],
    });
    if (path.endsWith("/pdf-preview")) return route.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\n%%EOF" });
    if (path === "/api/order-requests/templates/create") {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      template = { id: "template-1", name: body.name, project_name: JSON.parse(body.content.request_conditions).project_name,
        source_document_number: "", payload: body.content };
      return respond(template);
    }
    if (path === "/api/order-requests/templates") {
      if (method === "POST") {
        const body = route.request().postDataJSON();
        const copied = JSON.parse(version.request_conditions);
        copied.work_period = { from: "", to: "", excluded_dates: [] };
        copied.schedule.work_groups.forEach((group: any) => Object.assign(group, { from: "", to: "", excluded_dates: [] }));
        copied.schedule.rate_groups.forEach((group: any) => Object.assign(group, { from: "", to: "" }));
        template = { id: "template-1", name: body.name, project_name: "確認用イベント", source_document_number: version.document_number,
          payload: { kind: "formal", work_date_label: "", site_name: "会場", request_conditions: JSON.stringify(copied), body: "", contact_name: "なし", worker_ids: [], recipient_absences: {}, follow_up_due_on: null } };
        return respond(template);
      }
      const search = new URL(route.request().url()).searchParams.get("q") || "";
      const items = template && template.name.includes(search) ? [template] : [];
      return respond({ items, total: items.length });
    }
    if (path === "/api/order-requests/templates/template-1/archive") { template = null; return respond({ id: "template-1", archived: true }); }
    if (path === "/api/order-requests/templates/template-1") return respond(template);
    if (path === "/api/order-requests/versions/version-1") {
      if (method === "PATCH") {
        const body = route.request().postDataJSON(); writes.push({ path, body });
        return respond({ ...version, ...body });
      }
      return respond(version);
    }
    if (path === "/api/order-requests") return respond({ items: [{ ...version, version_id: version.id, project_name: "確認用イベント", categories: ["フェス系", "研修"], recipient_count: 1, send_state: "saved_unsent" }], total: 1, line_send_available: true });
    if (path === "/api/workers") return respond({ items: [{ id: "worker-1", name: "稼働者1", tags: [], is_active: true }], total: 1 });
    return respond({ items: [], total: 0 });
  });
  return writes;
}

test("order name and reference URL stay separate and postal lookup preserves manual addresses", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  await page.route("https://zipcloud.ibsnet.co.jp/api/search?*", async (route) => {
    const postal = new URL(route.request().url()).searchParams.get("zipcode");
    if (postal === "1000001") await new Promise((resolve) => setTimeout(resolve, 700));
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: 200, results: [{ zipcode: postal, address1: "神奈川県", address2: "横浜市中区", address3: "新港" }] }) });
  });
  await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "テンプレートの作成", exact: true }).click();
  const editor = page.getByRole("dialog", { name: "テンプレートの作成", exact: true });
  await editor.getByRole("textbox", { name: "テンプレート名（必須）", exact: true }).fill("URLと住所");
  await editor.getByRole("textbox", { name: "案件名", exact: true }).fill("案内イベント");
  await editor.getByRole("textbox", { name: "参考URL（任意）", exact: true }).fill("https://example.com/~event");
  await editor.getByRole("textbox", { name: "稼働場所", exact: true }).fill("会場名のみ");
  await expect(editor.getByRole("textbox", { name: "稼働場所", exact: true })).toHaveAttribute("placeholder", "会場名");
  const nameCard = await editor.locator(".order-project-field").boundingBox();
  const category = await editor.locator(".order-category-field").boundingBox();
  expect(Math.abs(nameCard!.y - category!.y)).toBeLessThan(24);
  expect(Math.abs(nameCard!.width - category!.width)).toBeLessThan(2);
  expect(category!.x).toBeGreaterThan(nameCard!.x + nameCard!.width);
  const postal = editor.getByRole("textbox", { name: "稼働場所の郵便番号", exact: true });
  const postalLabel = await editor.locator(".order-postal-heading > label").boundingBox();
  const postalHint = await editor.locator(".order-postal-heading > .order-field-hint").boundingBox();
  expect(postalHint!.x).toBeGreaterThan(postalLabel!.x + postalLabel!.width);
  expect(Math.abs(postalHint!.y - postalLabel!.y)).toBeLessThan(10);
  const address = editor.getByRole("textbox", { name: "稼働場所の住所", exact: true });
  await postal.fill("２３１－０００１");
  await expect(address).toHaveValue("〒231-0001 神奈川県横浜市中区新港");
  await address.fill("〒231-0001 神奈川県横浜市中区新港1-1 会場ビル3F");
  await postal.fill("1000001");
  await expect(editor.getByRole("status")).toContainText("住所を検索中");
  await address.fill("主催者確認済みの住所・建物名");
  await expect(editor.getByRole("status")).toContainText("自動で変更しません");
  await expect(address).toHaveValue("主催者確認済みの住所・建物名");
  await page.screenshot({ path: testInfo.outputPath("order-name-url-address.png") });
  await editor.getByRole("button", { name: "テンプレートを作成", exact: true }).click();
  await expect(editor).toHaveCount(0);
  const content = writes[0].body.content;
  expect(JSON.parse(content.request_conditions).reference_url).toBe("https://example.com/~event");
  expect(JSON.parse(content.request_conditions).project_name).toBe("案内イベント");
  expect(content.site_name).toBe("会場名のみ");
  expect(content.site_address).toBe("主催者確認済みの住所・建物名");
  await page.getByRole("button", { name: "保存済みテンプレート", exact: true }).click();
  await page.getByRole("button", { name: "このテンプレートで新規作成", exact: true }).click();
  const draft = page.getByRole("dialog", { name: "新規の下書き", exact: true });
  await expect(draft.getByRole("textbox", { name: "参考URL（任意）", exact: true })).toHaveValue("https://example.com/~event");
  await expect(draft.getByRole("textbox", { name: "案件名", exact: true })).toHaveAttribute("aria-required", "true");
});

test("settings replaces the top bar and keeps theme across navigation with compact profile forms", async ({ page }, testInfo) => {
  await adminMocks(page);
  await page.goto("/operations/order-requests");
  await expect(page.locator(".topbar")).toHaveCount(0);
  await expect(page.getByText("弁護士確認済み書式のレイアウトは未適用です。", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "登録画面のURL確認", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "ダークモードに切り替え", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "adminの設定・プロフィール", exact: true }).click();
  await expect(page.getByRole("heading", { name: "設定・プロフィール", exact: true })).toBeVisible();
  const profile = page.locator(".account-profile");
  expect((await profile.boundingBox())!.width).toBeLessThanOrEqual(720);
  const save = page.getByRole("button", { name: "保存", exact: true });
  expect((await save.boundingBox())!.width).toBeLessThan(160);
  await page.getByRole("button", { name: "ダークモード", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({ path: testInfo.outputPath("compact-settings-dark.png"), fullPage: true });
  await page.getByRole("button", { name: "登録画面のURL確認", exact: true }).click();
  const urls = page.getByRole("dialog", { name: "登録画面のURL一覧", exact: true });
  await expect(urls.getByText("稼働者登録", { exact: true })).toBeVisible();
  await urls.getByRole("button", { name: "閉じる", exact: true }).click();
  await page.getByRole("link", { name: "発注依頼書", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.goto("/account/profile");
  await page.getByRole("button", { name: "ライトモード", exact: true }).click();
  await expect(page.getByRole("button", { name: "ライトモード", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: testInfo.outputPath("compact-settings-light.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(profile).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: testInfo.outputPath("compact-settings-mobile.png"), fullPage: true });
});

test("direct template creation stores reusable content without creating or sending an order", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "テンプレートの作成", exact: true }).click();
  const editor = page.getByRole("dialog", { name: "テンプレートの作成", exact: true });
  await editor.getByRole("textbox", { name: "テンプレート名（必須）", exact: true }).fill("毎月の基本テンプレート");
  await editor.getByRole("textbox", { name: "案件名", exact: true }).fill("毎月の案内イベント");
  await editor.getByRole("textbox", { name: "稼働場所", exact: true }).fill("検証用会場");
  await editor.getByLabel("開始時間", { exact: true }).fill("09:00");
  await editor.getByLabel("終了時間", { exact: true }).fill("17:00");
  await editor.getByRole("spinbutton", { name: "単価（円・税抜）", exact: true }).fill("15000");
  await editor.getByRole("radio", { name: "インセンティブあり", exact: true }).check();
  await editor.getByRole("textbox", { name: "インセンティブの詳細", exact: true }).fill("販売1台につき500円");
  await expect(editor.getByRole("button", { name: "稼働日の開始", exact: true })).toHaveCount(0);
  await expect(editor.getByText("送付と追跡", { exact: true })).toHaveCount(0);
  await expect(editor.getByText("送付先", { exact: true })).toHaveCount(0);
  await expect(editor.getByRole("button", { name: "保存", exact: true })).toHaveCount(0);
  await expect(editor.getByRole("button", { name: "PDFを確認して送付する", exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("direct-template-editor.png") });
  await editor.getByRole("button", { name: "テンプレートを作成", exact: true }).click();
  await expect(editor).toHaveCount(0);
  expect(writes).toHaveLength(1);
  expect(writes[0].path).toBe("/api/order-requests/templates/create");
  await page.getByRole("button", { name: "保存済みテンプレート", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "保存済みテンプレート", exact: true });
  await expect(picker.getByText("直接作成", { exact: true })).toBeVisible();
  await picker.getByRole("button", { name: "このテンプレートで新規作成", exact: true }).click();
  const draft = page.getByRole("dialog", { name: "新規の下書き", exact: true });
  await expect(draft.getByRole("textbox", { name: "案件名", exact: true })).toHaveValue("毎月の案内イベント");
  await expect(draft.getByRole("button", { name: "稼働日の開始", exact: true })).toContainText("日付を選択");
  await expect(draft.getByRole("spinbutton", { name: "単価（円・税抜）", exact: true })).toHaveValue("15000");
  await expect(draft.getByRole("textbox", { name: "インセンティブの詳細", exact: true })).toHaveValue("販売1台につき500円");
  await expect(draft.getByText("まだ送付先は選ばれていません。", { exact: true })).toBeVisible();
});

test("new order defaults to no incentive and only yes exposes an empty conditions field", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成", exact: true }).click();
  const draft = page.getByRole("dialog", { name: "新規の下書き", exact: true });
  await expect(draft.getByRole("radio", { name: "インセンティブなし", exact: true })).toBeChecked();
  await expect(draft.getByText("インセンティブなし", { exact: true })).toBeVisible();
  await expect(draft.getByRole("textbox", { name: "インセンティブの詳細", exact: true })).toHaveCount(0);
  await draft.getByRole("radio", { name: "インセンティブあり", exact: true }).check();
  const details = draft.getByRole("textbox", { name: "インセンティブの詳細", exact: true });
  await expect(details).toHaveValue("");
  await details.fill("販売1台につき500円\n翌月に販売実績確定");
  await page.screenshot({ path: testInfo.outputPath("order-incentive-toggle.png") });
  await draft.getByRole("radio", { name: "インセンティブなし", exact: true }).check();
  await expect(details).toHaveCount(0);
  await expect(draft.getByText("インセンティブなし", { exact: true })).toBeVisible();
  await draft.getByRole("radio", { name: "インセンティブあり", exact: true }).check();
  await expect(details).toHaveValue("");
  expect(writes).toEqual([]);
});

test("worker calendar retains dates while scrolling; event document opens details", async ({ page }, testInfo) => {
  await adminMocks(page);
  await page.goto("/operations/calendar?view=worker&month=2026-10");
  const scroll = page.locator(".overview-scroll");
  await expect(page.getByText("稼働者44", { exact: true })).toBeAttached();
  const before = await page.locator(".overview-head-day").first().boundingBox();
  await scroll.evaluate((element) => { element.scrollTop = 800; element.scrollLeft = 500; });
  const after = await page.locator(".overview-head-day").first().boundingBox();
  expect(Math.abs(after!.y - before!.y)).toBeLessThan(2);
  expect(await scroll.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await page.screenshot({ path: testInfo.outputPath("calendar-scrolled.png") });
  await page.getByRole("tab", { name: "イベントごと", exact: true }).click();
  await expect(page.locator(".page-description")).toBeEmpty();
  await expect(page.getByText("表示不要な集合場所")).toHaveCount(0);
  const link = page.getByRole("button", { name: version.document_number, exact: true });
  await link.click();
  const dialog = page.getByRole("dialog", { name: /発注依頼書 ORD/ });
  await expect(dialog.getByText("会場の受付", { exact: false })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("calendar-document.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(link).toBeFocused();
});

test("saved template can be found and loaded into an independent blank-date draft", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "テンプレートとして保存", exact: true }).click();
  const save = page.getByRole("dialog", { name: "テンプレートとして保存", exact: true });
  await save.getByRole("textbox", { name: "テンプレート名", exact: true }).fill("季節のイベント");
  await save.getByRole("button", { name: "テンプレートを保存", exact: true }).click();
  await expect(save).toHaveCount(0);
  await page.getByRole("button", { name: "新規の依頼書を作成", exact: true }).click();
  await page.getByRole("button", { name: "テンプレートから呼び出す", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "保存済みテンプレート", exact: true });
  await picker.getByRole("textbox", { name: "テンプレート名で検索", exact: true }).fill("季節");
  await expect(picker.getByText("季節のイベント", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("template-picker.png") });
  await picker.getByRole("button", { name: "このテンプレートで新規作成", exact: true }).click();
  await expect(picker).toHaveCount(0);
  const draft = page.getByRole("dialog", { name: "新規の下書き", exact: true });
  await expect(draft.getByRole("textbox", { name: "案件名", exact: true })).toHaveValue("確認用イベント");
  await expect(draft.getByRole("button", { name: "稼働日の開始", exact: true })).toContainText("日付を選択");
  await expect(draft.getByRole("button", { name: "稼働日の終了", exact: true })).toContainText("日付を選択");
  await expect(draft.getByRole("spinbutton", { name: "単価（円・税抜）", exact: true })).toHaveValue("10000");
  await expect(draft.getByText("まだ送付先は選ばれていません。", { exact: true })).toBeVisible();
  await draft.getByRole("textbox", { name: "案件名", exact: true }).fill("今回だけ変更");
  await draft.getByRole("button", { name: "閉じる", exact: true }).click();
  await page.getByRole("button", { name: "保存済みテンプレート", exact: true }).click();
  await expect(picker.getByText("確認用イベント", { exact: true })).toBeVisible();
  await picker.getByRole("button", { name: "一覧から外す", exact: true }).click();
  const confirm = page.getByRole("dialog", { name: "テンプレートを一覧から外す", exact: true });
  await confirm.getByRole("button", { name: "一覧から外す", exact: true }).click();
  await expect(picker.getByText("季節のイベント", { exact: true })).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("confirmed cabinet holidays show only their names and the import record", async ({ page }, testInfo) => {
  await adminMocks(page);
  await page.route("**/api/order-requests/holiday-calendar?*", route => route.fulfill({ json: [
    { day: "2026-11-03", name: "文化の日", is_holiday: true, revision: 1, source: "cabinet_csv" },
    { day: "2026-11-23", name: "勤労感謝の日", is_holiday: true, revision: 1, source: "cabinet_csv" },
  ] }));
  await page.route("**/api/order-requests/holiday-calendar/import", route => route.fulfill({ json: {
    imported: true, needs_refresh: false, notice: null,
    label: "内閣府CSV取込：2026年11月16日、1955年1月〜2027年11月分",
  } }));
  await page.goto("/operations/order-requests");
  await page.locator(".is-created").getByRole("button", { name: version.document_number, exact: true }).click();
  await page.getByRole("button", { name: "稼働日の開始", exact: true }).click();
  const calendar = page.getByRole("dialog", { name: "稼働日の開始", exact: true });
  if (await calendar.getByRole("button", { name: "2026-11-03（文化の日）", exact: true }).count() === 0) {
    await calendar.getByRole("button", { name: "次の月", exact: true }).click();
  }
  const culture = calendar.getByRole("button", { name: "2026-11-03（文化の日）", exact: true });
  const labor = calendar.getByRole("button", { name: "2026-11-23（勤労感謝の日）", exact: true });
  await expect(culture).toHaveAttribute("title", "文化の日");
  await expect(labor).toHaveAttribute("title", "勤労感謝の日");
  await expect(calendar.getByText("未確認の祝日候補を含みます")).toHaveCount(0);
  await culture.hover();
  await page.screenshot({ path: testInfo.outputPath("holiday-names.png") });
  await page.keyboard.press("Escape");
  await page.getByRole("group", { name: "稼働日の詳細1の日付の設定" }).getByRole("button", { name: "毎週" }).click();
  await expect(page.getByText("内閣府CSV取込：2026年11月16日、1955年1月〜2027年11月分", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("holiday-import-record.png") });
});

test("order calendar colors confirmed holidays and weekends", async ({ page }) => {
  await adminMocks(page);
  await page.route("**/api/order-requests/holiday-calendar?*", route => route.fulfill({ json: [
    { day: "2026-10-31", is_holiday: true, revision: 1, name: "テストの日" },
    { day: "2026-10-30", is_holiday: false, revision: 1 },
    { day: "2026-10-29", is_holiday: true, revision: 0 },
  ] }));
  await page.goto("/operations/order-requests");
  await page.locator(".is-created").getByRole("button", { name: version.document_number, exact: true }).click();
  await page.getByRole("button", { name: "稼働日の詳細1の開始日", exact: true }).click();
  const calendar = page.getByRole("dialog", { name: "稼働日の詳細1の開始日", exact: true });
  await expect(calendar.getByRole("button", { name: "2026-10-31（テストの日）" })).toHaveClass(/is-holiday/);
  await expect(calendar.getByRole("button", { name: "2026-10-31（テストの日）" })).toHaveAttribute("title", "テストの日");
  await expect(calendar.getByRole("button", { name: "2026-10-29（祝日候補・要確認）" })).toHaveAttribute("title", "祝日候補・要確認");
  await expect(calendar.getByRole("button", { name: "2026-10-30" })).not.toHaveClass(/is-holiday/);
  await expect(calendar.getByRole("button", { name: "2026-10-29（祝日候補・要確認）" })).toHaveClass(/is-holiday/);
  await expect(calendar.getByText("赤い日には未確認の祝日候補を含みます。祝日一覧で確認してください。")).toBeVisible();
  await expect(calendar.locator(".month-calendar-weekday.is-sat")).toHaveText("土");
  await expect(calendar.locator(".month-calendar-weekday.is-sun")).toHaveText("日");
  await calendar.getByRole("button", { name: "次の月" }).click();
  await expect(calendar.getByRole("button", { name: "2026-11-01" })).toHaveClass(/is-holiday/);
  await expect(calendar.getByRole("button", { name: "2026-11-07" })).toHaveClass(/is-saturday/);
});

test("form layout and detail dates stay within the overall work period", async ({ page }, testInfo) => {
  await adminMocks(page);
  await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成", exact: true }).click();
  const draft = page.getByRole("dialog", { name: "新規の下書き", exact: true });
  const meeting = await draft.getByRole("textbox", { name: "集合場所（任意）", exact: true }).locator("..").boundingBox();
  const station = await draft.getByRole("textbox", { name: "会場の最寄り駅（任意）", exact: true }).locator("..").boundingBox();
  const walk = await draft.getByRole("spinbutton", { name: "駅から徒歩（分）", exact: true }).locator("..").boundingBox();
  const period = await draft.locator(".order-work-period-field").boundingBox();
  expect(Math.abs(meeting!.y - station!.y)).toBeLessThan(2);
  expect(Math.abs(meeting!.y - walk!.y)).toBeLessThan(2);
  expect(station!.x).toBeGreaterThan(meeting!.x + meeting!.width);
  expect(walk!.x).toBeGreaterThan(station!.x + station!.width);
  expect(Math.abs(period!.x - meeting!.x)).toBeLessThan(2);
  expect(period!.y).toBeGreaterThan(meeting!.y + meeting!.height);
  await draft.locator(".order-meeting-row").screenshot({ path: testInfo.outputPath("aligned-meeting-fields.png") });
  await expect(draft.getByRole("button", { name: "稼働日の詳細1の開始日", exact: true })).toBeDisabled();
  const templateButton = draft.getByRole("button", { name: "テンプレートから呼び出す", exact: true });
  await expect(templateButton).toHaveClass(/btn-line-blue/);
  const site = await draft.getByRole("textbox", { name: "稼働場所", exact: true }).boundingBox();
  const background = await draft.getByRole("textbox", { name: "背景", exact: true }).boundingBox();
  expect(background!.x).toBeGreaterThan(site!.x);
  expect(Math.abs(background!.y - site!.y)).toBeLessThan(2);
  expect(Math.abs(background!.width - site!.width)).toBeLessThan(2);
  const memo = draft.getByRole("textbox", { name: /取引相手メモ/ });
  const memoBox = await memo.boundingBox();
  const grid = await memo.locator("..").locator("..").boundingBox();
  expect(Math.abs(memoBox!.x + memoBox!.width - grid!.x - grid!.width)).toBeLessThan(2);
  await expect(memo.locator("..").locator(".order-field-hint")).toHaveText("PDFには記載しません");
  await expect(draft.locator(".order-field-hint").getByText("（保存は空でも可。送付のときに決めます）", { exact: true })).toBeVisible();
  await expect(draft.getByText("期限内に返事がない相手へ案内を送ります", { exact: true })).toBeVisible();
  const phone = draft.getByRole("checkbox", { name: /電話先行/ });
  const phoneMemo = draft.getByRole("textbox", { name: "電話メモ", exact: true });
  await expect(phoneMemo).toHaveCount(0);
  await phone.check();
  await phoneMemo.fill("折り返し待ち");
  const phoneBox = await phone.locator("..").boundingBox();
  const phoneMemoBox = await phoneMemo.boundingBox();
  expect(phoneMemoBox!.x).toBeGreaterThan(phoneBox!.x + phoneBox!.width);
  await phone.uncheck();
  await expect(phoneMemo).toHaveCount(0);
  await phone.check();
  await expect(phoneMemo).toHaveValue("折り返し待ち");
  await page.screenshot({ path: testInfo.outputPath("order-contact-layout.png") });
  await draft.getByRole("button", { name: "閉じる", exact: true }).click();

  await page.locator(".is-created").getByRole("button", { name: version.document_number, exact: true }).click();
  await page.getByRole("button", { name: "稼働日の詳細1の開始日", exact: true }).click();
  const start = page.getByRole("dialog", { name: "稼働日の詳細1の開始日", exact: true });
  await expect(start.getByRole("button", { name: "2026-10-28", exact: true })).toBeDisabled();
  await expect(start.getByRole("button", { name: "2026-10-29", exact: true })).toBeEnabled();
  await expect(start.getByRole("button", { name: "前の月", exact: true })).toBeDisabled();
  await start.getByRole("button", { name: "次の月", exact: true }).click();
  await expect(start.getByRole("button", { name: "2026-11-04", exact: true })).toBeEnabled();
  await expect(start.getByRole("button", { name: "2026-11-05", exact: true })).toBeDisabled();
  await expect(start.getByRole("button", { name: "次の月", exact: true })).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "稼働日の終了", exact: true }).click();
  const overall = page.getByRole("dialog", { name: "稼働日の終了", exact: true });
  await overall.getByRole("button", { name: "前の月", exact: true }).click();
  await overall.getByRole("button", { name: "2026-10-30", exact: true }).click();
  await page.getByRole("button", { name: "稼働日の詳細1の終了日", exact: true }).click();
  const end = page.getByRole("dialog", { name: "稼働日の詳細1の終了日", exact: true });
  await expect(end.getByRole("button", { name: "2026-10-28", exact: true })).toBeDisabled();
  await expect(end.getByRole("button", { name: "2026-10-30", exact: true })).toBeEnabled();
  await expect(end.getByRole("button", { name: "2026-10-31", exact: true })).toBeDisabled();
  await expect(end.getByRole("button", { name: "次の月", exact: true })).toBeDisabled();
  await end.getByRole("button", { name: "2026-10-30", exact: true }).click();
  await expect(page.getByRole("button", { name: "稼働日の詳細1の終了日", exact: true })).toContainText("2026/10/30");
});

test("weekly conditions are weekday and holiday buttons; the holiday row always overrides and the snapshot is saved", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  const candidates = [{ day: "2026-11-03", name: "文化の日", is_holiday: true, revision: 0, source: "library" }];
  await page.route("**/api/order-requests/holiday-calendar**", async (route) => {
    const isConfirm = new URL(route.request().url()).pathname.endsWith("/confirm");
    if (isConfirm) expect(route.request().postDataJSON().days).toEqual(["2026-11-03"]);
    return route.fulfill({ contentType: "application/json", body: JSON.stringify(isConfirm ? candidates.map((v) => ({ ...v, revision: 1 })) : candidates) });
  });
  await page.goto("/operations/order-requests");
  await page.locator(".is-created").getByRole("button", { name: version.document_number, exact: true }).click();
  const mode = (n: number) => page.getByRole("group", { name: `稼働日の詳細${n}の日付の設定` });
  const buttons = (n: number) => page.getByRole("group", { name: `稼働日の詳細${n}の曜日と祝日` });
  await mode(1).getByRole("button", { name: "毎週" }).click();
  // 標準では開始日・終了日を出さず、曜日と祝日の8つのボタンだけ
  await expect(page.getByRole("button", { name: "稼働日の詳細1の開始日", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "稼働日の詳細1の終了日", exact: true })).toHaveCount(0);
  await expect(buttons(1).getByRole("button")).toHaveText(["月", "火", "水", "木", "金", "土", "日", "祝日"]);
  await expect(page.getByRole("checkbox", { name: /祝日もこの条件に含める/ })).toHaveCount(0);
  for (const day of ["月", "火", "水", "木", "金"]) await buttons(1).getByRole("button", { name: day, exact: true }).click();
  await page.getByRole("button", { name: "稼働日・期間を追加" }).click();
  await mode(2).getByRole("button", { name: "毎週" }).click();
  for (const day of ["土", "日"]) await buttons(2).getByRole("button", { name: day, exact: true }).click();
  await page.getByRole("button", { name: "稼働日・期間を追加" }).click();
  await mode(3).getByRole("button", { name: "毎週" }).click();
  await buttons(3).getByRole("button", { name: "祝日", exact: true }).click();
  const third = page.getByRole("group", { name: "稼働日の詳細 3" });
  await third.getByLabel("開始時間").fill("08:00");
  await third.getByLabel("終了時間").fill("19:00");
  await page.getByRole("group", { name: /単価 3/ }).getByRole("spinbutton", { name: "単価（円・税抜）" }).fill("20000");
  // 期間を区切るときだけ開始日・終了日が出る
  await page.getByRole("group", { name: "稼働日の詳細 3" }).getByRole("checkbox", { name: "期間を区切る（開始日・終了日を指定）" }).check();
  await expect(page.getByRole("button", { name: "稼働日の詳細3の開始日", exact: true })).toBeVisible();
  await page.getByRole("group", { name: "稼働日の詳細 3" }).getByRole("checkbox", { name: "期間を区切る（開始日・終了日を指定）" }).uncheck();
  await expect(page.getByRole("button", { name: "稼働日の詳細3の開始日", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "祝日一覧を確認", exact: true }).click();
  await expect(page.getByText("2026-11-03 文化の日 祝日")).toBeVisible();
  await page.getByRole("button", { name: "この一覧を確認して依頼書に反映", exact: true }).click();
  await expect(page.getByText("祝日一覧を依頼書に反映しました。日付と条件を確認してください。")).toBeVisible();
  const shot = (name: string) => process.env.SHOT_DIR ? `${process.env.SHOT_DIR}/${name}` : testInfo.outputPath(name);
  await page.getByRole("group", { name: "稼働日の詳細 1" }).screenshot({ path: shot("weekly-row1.png") });
  await page.getByRole("group", { name: "稼働日の詳細 3" }).screenshot({ path: shot("weekly-row3.png") });
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  const written = JSON.parse(writes[0].body.request_conditions).schedule;
  expect(written.work_groups[0]).toMatchObject({ date_mode: "weekly", weekly_rule: "v2", custom_range: false, weekdays: [0, 1, 2, 3, 4], holiday_selected: false, holiday_dates: ["2026-11-03"], holiday_skip: ["2026-11-03"] });
  expect(written.work_groups[1]).toMatchObject({ weekdays: [5, 6], holiday_selected: false, holiday_skip: [] });
  expect(written.work_groups[2]).toMatchObject({ weekdays: [], holiday_selected: true, holiday_dates: ["2026-11-03"], start_time: "08:00", end_time: "19:00" });
  expect(written.rate_groups[2]).toMatchObject({ amount: "20000", weekly_rule: "v2", holiday_selected: true });
  expect(written.rate_groups[0].holiday_skip).toEqual(["2026-11-03"]);
});

test("weekly rows warn about overlaps before saving and ask before saving days without a condition", async ({ page }) => {
  const writes = await adminMocks(page);
  await page.route("**/api/order-requests/holiday-calendar**", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.goto("/operations/order-requests");
  await page.locator(".is-created").getByRole("button", { name: version.document_number, exact: true }).click();
  const mode = (n: number) => page.getByRole("group", { name: `稼働日の詳細${n}の日付の設定` });
  const buttons = (n: number) => page.getByRole("group", { name: `稼働日の詳細${n}の曜日と祝日` });
  await mode(1).getByRole("button", { name: "毎週" }).click();
  for (const day of ["月", "火", "水"]) await buttons(1).getByRole("button", { name: day, exact: true }).click();
  await page.getByRole("button", { name: "稼働日・期間を追加" }).click();
  await mode(2).getByRole("button", { name: "毎週" }).click();
  for (const day of ["水", "木"]) await buttons(2).getByRole("button", { name: day, exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "「水」が重なっています" })).toBeVisible();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "稼働日の詳細1と2で「水」が重なっています" }).last()).toBeVisible();
  expect(writes).toHaveLength(0);
  await buttons(2).getByRole("button", { name: "水", exact: true }).click();
  await expect(page.getByText("土・日に当たる日の条件がありません", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  const ask = page.getByRole("dialog", { name: "稼働しない曜日・祝日があります" });
  await expect(ask).toBeVisible();
  await ask.getByRole("button", { name: "キャンセル" }).click();
  expect(writes).toHaveLength(0);
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await page.getByRole("dialog", { name: "稼働しない曜日・祝日があります" }).getByRole("button", { name: "この内容で保存" }).click();
  await expect.poll(() => writes.length).toBe(1);
});

test("order calendars mark today in Japan time without replacing selection or weekend colors", async ({ page }, testInfo) => {
  await page.clock.install({ time: new Date("2026-11-16T03:00:00Z") });
  await adminMocks(page);
  await page.goto("/operations/order-requests");
  await page.locator(".is-created").getByRole("button", { name: version.document_number, exact: true }).click();
  await page.getByRole("button", { name: "稼働日の開始", exact: true }).click();
  const start = page.getByRole("dialog", { name: "稼働日の開始", exact: true });
  if (await start.getByRole("button", { name: "2026-11-16", exact: true }).count() === 0) {
    await start.getByRole("button", { name: "次の月", exact: true }).click();
  }
  const today = start.getByRole("button", { name: "2026-11-16", exact: true });
  const saturday = start.getByRole("button", { name: "2026-11-14", exact: true });
  const sunday = start.getByRole("button", { name: "2026-11-15", exact: true });
  await expect(today).toHaveClass(/is-today/);
  await expect(today).toHaveCSS("border-top-color", "rgb(22, 163, 74)");
  await expect(today).toHaveCSS("box-shadow", "rgb(22, 163, 74) 0px 0px 0px 1px");
  await expect(saturday).not.toHaveClass(/is-today/);
  await expect(saturday).toHaveCSS("color", "rgb(29, 78, 216)");
  await expect(sunday).toHaveCSS("color", "rgb(185, 28, 28)");
  await page.screenshot({ path: testInfo.outputPath("today-open.png") });
  await today.click();
  await page.getByRole("button", { name: "稼働日の開始", exact: true }).click();
  const selectedToday = page.getByRole("dialog", { name: "稼働日の開始", exact: true }).getByRole("button", { name: "2026-11-16", exact: true });
  await expect(selectedToday).toHaveClass(/is-today/);
  await expect(selectedToday).toHaveClass(/is-selected/);
  await expect(selectedToday).toHaveCSS("background-color", "rgb(37, 99, 235)");
  await expect(selectedToday).toHaveCSS("border-top-color", "rgb(22, 163, 74)");
  await expect(selectedToday).toHaveCSS("color", "rgb(255, 255, 255)");
  await page.screenshot({ path: testInfo.outputPath("today-selected.png") });
  await selectedToday.click();
  await page.getByRole("button", { name: "稼働日の終了", exact: true }).click();
  await page.getByRole("dialog", { name: "稼働日の終了", exact: true }).getByRole("button", { name: "2026-11-30", exact: true }).click();
  await page.getByRole("button", { name: "休業日を変更", exact: true }).click();
  const closed = page.locator(".order-excluded-calendar");
  const closedToday = closed.getByRole("button", { name: "2026-11-16", exact: true });
  await expect(closedToday).toHaveClass(/is-today/);
  await expect(closedToday).not.toHaveClass(/is-off/);
  await expect(closed.locator("button.is-saturday span").first()).toHaveCSS("color", "rgb(29, 78, 216)");
  await closedToday.click();
  await expect(closedToday).toHaveClass(/is-today/);
  await expect(closedToday).toHaveClass(/is-off/);
  await expect(closedToday).toHaveCSS("border-top-color", "rgb(220, 38, 38)");
  await expect(closedToday).toHaveCSS("background-color", "rgb(253, 232, 232)");
  await expect(closedToday).toHaveCSS("box-shadow", "rgb(22, 163, 74) 0px 0px 0px 2px");
  await page.screenshot({ path: testInfo.outputPath("today-closed.png") });
});

test("saving sends nothing; the send step decides recipients and deadline before the PDF check", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  const requests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) requests.push(`${request.method()} ${new URL(request.url()).pathname}`); });
  await page.goto("/operations/order-requests");
  const created = page.locator(".is-created");
  await expect(created.getByRole("columnheader", { name: "区分", exact: true })).toHaveCount(0);
  // 一覧では保存済み（未送付）と見分けられ、絞り込みもできる
  await expect(created.locator("td", { hasText: "保存済み（未送付）" }).first()).toBeVisible();
  await expect(created.getByRole("combobox", { name: "依頼書の一覧条件" }).getByRole("option")).toHaveText(["最新版", "保存済み（未送付）", "一部送付済み", "送付済み", "結果不明", "未受領", "期限超過"]);
  await created.getByRole("button", { name: version.document_number, exact: true }).click();
  await page.getByRole("button", { name: "稼働日の開始", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "稼働日の開始", exact: true });
  await expect(picker.locator(".month-calendar-weekday").first()).toHaveText("月");
  await page.keyboard.press("Escape");
  await expect(picker).toHaveCount(0);
  // 保存だけでは送付しない
  await page.getByRole("textbox", { name: "案件名", exact: true }).fill("修正したイベント");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("保存しました。まだ誰にも送っていません。送付は「送付へ進む」で別に行います。")).toBeVisible();
  expect(writes).toHaveLength(1);
  expect(requests.filter((line) => /confirm|line-send/.test(line))).toEqual([]);
  // 送付は別の操作：送付先・期限を決めてからPDFを確認する
  await page.locator(".order-draft-foot").getByRole("button", { name: "送付へ進む", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "送付の設定", exact: true });
  await expect(settings).toBeVisible();
  await expect(settings.getByText("まだ誰にも送っていません。", { exact: false })).toBeVisible();
  await expect(settings.getByText("送付先", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("send-settings.png") });
  await settings.getByRole("button", { name: "PDFを確認する", exact: true }).click();
  await expect(settings.getByText("過ぎています", { exact: false })).toBeVisible();
  await settings.getByLabel("期限の案内（必須）").fill("2027-12-01");
  await settings.getByRole("button", { name: "PDFを確認する", exact: true }).click();
  const pdf = page.getByRole("dialog", { name: "PDFの確認", exact: true });
  await expect(pdf.getByRole("button", { name: "今すぐ送付する", exact: true })).toBeVisible();
  await pdf.getByRole("button", { name: "送付先・期限に戻る", exact: true }).click();
  await expect(settings).toBeVisible();
  await settings.getByRole("button", { name: "編集に戻る（保存済み）", exact: true }).click();
  await expect(settings).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "案件名", exact: true })).toHaveValue("修正したイベント");
  expect(requests.filter((line) => /confirm|line-send/.test(line))).toEqual([]);
  expect(writes[writes.length - 1].body.follow_up_due_on).toBe("2027-12-01");
  expect(writes[writes.length - 1].body.body).toContain("修正したイベント");
  expect(writes.every((write) => write.path.endsWith("/version-1"))).toBe(true);
});

test("all offered days start selected; unavailable days can be removed across months before sending", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    (window as any).liff = { init: async () => {}, isLoggedIn: () => true, getIDToken: () => "id-test", isInClient: () => false };
  });
  const offered = ["2026-10-29", "2026-10-31", "2026-11-01", "2026-11-02", "2026-11-04"];
  const working = [...offered, "2026-11-03"];
  const submissions: any[] = [];
  await page.route("**/api/line/worker/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/entry")) return respond({ liff_id: "test-liff" });
    if (path.endsWith("/sessions")) return respond({ token: "worker-token" });
    if (route.request().method() === "POST") { submissions.push(route.request().postDataJSON()); return respond({ outcome: "acked" }); }
    return respond({ delivery_id: "delivery-1", document_number: version.document_number, version_no: 1, project_name: "確認用イベント", state: "open", offered_dates: offered, holidays: ["2026-10-30"], period: { from: "2026-10-29", to: "2026-11-04" }, work_days: working.map((date) => ({ date, start_time: "09:00", end_time: "17:00" })), accepted_dates: [], today: "2026-10-23" });
  });
  await page.goto("/public/line-worker?m=pick&d=delivery-1");
  await expect(page.locator(".lw-footer-dates")).toHaveText("5日を選択しています");
  await expect(page.getByRole("button", { name: "すべて選択する", exact: true })).toHaveCount(0);
  expect(submissions).toEqual([]);
  const october29 = page.locator(".lw-day").filter({ has: page.getByText("29", { exact: true }) });
  await october29.click();
  await expect(page.locator(".lw-footer-dates")).toHaveText("4日を選択しています");
  await october29.click();
  await page.getByRole("button", { name: "次の月", exact: true }).click();
  await page.locator(".lw-day").filter({ has: page.getByText("4", { exact: true }) }).click();
  await page.getByRole("button", { name: "確認する", exact: true }).click();
  await expect(page.locator(".lw-dates")).toHaveText("10月29日（木）\n10月31日（土）〜11月2日（月）");
  const off = page.getByRole("heading", { name: "参加しない日", exact: true }).locator("+ p");
  await expect(off).toHaveText("11月3日（火）〜11月4日（水）");
  await expect(page.getByRole("heading", { name: "期間中の休業日", exact: true }).locator("+ p")).toHaveText("10月30日（金）");
  await page.screenshot({ path: testInfo.outputPath("participation-confirm.png"), fullPage: true });
  await page.getByRole("button", { name: "送信", exact: true }).click();
  await expect(page.getByRole("heading", { name: "送信しました", exact: true })).toBeVisible();
  expect(submissions[0].dates).toEqual(offered.filter((day) => day !== "2026-11-04"));
});
