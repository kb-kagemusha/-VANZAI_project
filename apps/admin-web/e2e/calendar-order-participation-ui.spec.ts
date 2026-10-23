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
    if (path === "/api/order-requests") return respond({ items: [{ ...version, version_id: version.id, project_name: "確認用イベント", categories: ["フェス系", "研修"], recipient_count: 1 }], total: 1, line_send_available: true });
    if (path === "/api/workers") return respond({ items: [{ id: "worker-1", name: "稼働者1", tags: [], is_active: true }], total: 1 });
    return respond({ items: [], total: 0 });
  });
  return writes;
}

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
  await expect(editor.getByRole("button", { name: "下書きを保存", exact: true })).toHaveCount(0);
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

test("form layout and detail dates stay within the overall work period", async ({ page }, testInfo) => {
  await adminMocks(page);
  await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成", exact: true }).click();
  const draft = page.getByRole("dialog", { name: "新規の下書き", exact: true });
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
  await expect(draft.getByText("（必須）", { exact: true })).toBeVisible();
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

test("Monday date picker and PDF correction preserve draft and reuse its id", async ({ page }, testInfo) => {
  const writes = await adminMocks(page);
  await page.goto("/operations/order-requests");
  const created = page.locator(".is-created");
  await expect(created.getByRole("columnheader", { name: "区分", exact: true })).toHaveCount(0);
  await created.getByRole("button", { name: version.document_number, exact: true }).click();
  await page.getByRole("button", { name: "稼働日の開始", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "稼働日の開始", exact: true });
  await expect(picker.locator(".month-calendar-weekday").first()).toHaveText("月");
  await page.screenshot({ path: testInfo.outputPath("monday-picker.png") });
  await page.keyboard.press("Escape");
  await expect(picker).toHaveCount(0);
  await expect(page.getByRole("button", { name: "稼働日の開始", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "PDFを確認して送付する", exact: true }).click();
  const pdf = page.getByRole("dialog", { name: "PDFの確認", exact: true });
  await expect(pdf.getByRole("button", { name: "修正する", exact: true })).toBeVisible();
  await pdf.getByRole("button", { name: "修正する", exact: true }).click();
  await expect(pdf).toHaveCount(0);
  const project = page.getByRole("textbox", { name: "案件名", exact: true });
  await expect(project).toHaveValue("確認用イベント");
  await project.fill("修正したイベント");
  await page.getByRole("button", { name: "PDFを確認して送付する", exact: true }).click();
  await expect(pdf.getByRole("button", { name: "修正する", exact: true })).toBeVisible();
  expect(writes).toHaveLength(2);
  expect(writes[1].body.body).toContain("修正したイベント");
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
