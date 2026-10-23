import { expect, test, type Page } from "@playwright/test";

test.use({ viewport: { width: 1440, height: 1000 } });

async function mocks(page: Page, role = "admin", stale = false, incentive = false) {
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "test-token"));
  const writes: any[] = [];
  const calls: string[] = [];
  let saved = false;
  let savedIncentive: string | null = null;
  let invoice: any = null;
  let issuer = { revision: 1, name: "株式会社VANZAI", postal_code: "116-0002", address: "東京都荒川区荒川1丁目39-11 東京アルバタワー1703", registration_number: "", bank_details: "", payment_terms: "" };
  const order = { version_id: "v1", series_id: "s1", document_number: "ORD-001", version_no: 1,
    project_name: "秋のイベント", work_date_label: "10月30日～11月2日", client_id: "c1", client_name: "依頼元会社",
    revision: 0, amount_id: null, amount: null, billing_month: null, invoice_id: null, status: "missing",
    incentive_enabled: incentive, incentive_note: incentive ? "販売1台につき500円\n翌月実績確定" : "インセンティブなし", incentive_amount: null, total_amount: null, billing_ready: false, client_mismatch: false };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const method = route.request().method();
    const reply = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return reply({ id: role, username: role, role, is_active: true, permissions: ["invoice_read", "invoice_generate", "order_read"] });
    if (path.endsWith("/auth/session")) return reply({ access_token: "test-token", token_type: "bearer" });
    if (path.startsWith("/api/order-billing")) calls.push(path);
    if (method === "POST" || method === "PUT") writes.push({ path, body: route.request().postData() ? route.request().postDataJSON() : null });
    if (path.endsWith("/order-billing/issuer")) {
      if (method === "PUT") { const { expected_revision, ...values } = route.request().postDataJSON(); issuer = { ...values, revision: expected_revision + 1 }; }
      return reply(issuer);
    }
    if (path.endsWith("/order-billing/summary")) return reply({ missing_count: saved && (!incentive || savedIncentive !== null) ? 0 : 1, total: 1 });
    if (path.endsWith("/order-billing/clients")) return reply({ items: [{ id: "c1", name: "依頼元会社" }] });
    if (path.endsWith("/orders/v1/confirm")) {
      if (stale) return reply({ detail: "別の操作で金額が更新されました。一覧を更新して確認してください" }, 409);
      saved = true; savedIncentive = route.request().postDataJSON().incentive_amount; return reply({ id: "a1", revision: 1 });
    }
    if (path.endsWith("/order-billing/orders")) {
      const complete = saved && (!incentive || savedIncentive !== null);
      return reply({ items: complete ? [] : [{ ...order, ...(saved ? { amount_id: "a1", amount: "10001.00", revision: 1, billing_month: "202611" } : {}) }], total: complete ? 0 : 1 });
    }
    if (path.endsWith("/order-billing/invoices")) {
      if (method === "POST") {
        invoice = { id: "i1", document_number: "OB-202611-001", client_id: "c1", client_name: "依頼元会社", billing_month: "202611",
          billing_date: "2026-11-30", status: "draft", version: 1, subtotal: "10001.00", tax_amount: "1000.00", total_amount: "11001.00", issuer_snapshot: { ...issuer },
          lines: [{ id: "l1", document_number: "ORD-001", description: "秋のイベント", work_date_label: "10月30日～11月2日", amount: "10001.00" }] };
        return reply(invoice);
      }
      return reply({ items: invoice ? [invoice] : [], total: invoice ? 1 : 0 });
    }
    if (path.endsWith("/invoices/i1/issue")) { invoice.status = "issued"; return reply(invoice); }
    if (path.endsWith("/invoices/i1")) return reply(invoice);
    return reply({ items: [], total: 0 });
  });
  return { writes, calls };
}

test("admin selects billing month explicitly, saves total, clears red badge, creates and issues monthly draft", async ({ page }, testInfo) => {
  const state = await mocks(page);
  await page.goto("/billing/order-amounts");
  const nav = page.getByRole("link", { name: "依頼書の金額確定 未入力1件", exact: true });
  await expect(nav.locator(".nav-unread-badge")).toHaveText("1");
  await page.getByRole("button", { name: "サイドバーを縮小" }).click();
  await expect(nav.locator(".nav-unread-badge")).toBeVisible();
  await page.getByRole("button", { name: "請求金額を確定", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "依頼書の請求金額を確定", exact: true });
  await expect(edit.getByRole("combobox")).toHaveCount(0);
  await expect(edit.getByRole("textbox", { name: "請求先（案件のクライアント・変更不可）", exact: true })).toHaveValue("依頼元会社");
  await expect(edit.getByRole("textbox", { name: "請求先（案件のクライアント・変更不可）", exact: true })).toHaveAttribute("readonly", "");
  await expect(edit.getByRole("textbox", { name: "インセンティブ金額（税抜・円）", exact: true })).toHaveCount(0);
  await expect(edit.getByLabel("請求月（必須）")).toHaveValue("");
  await expect(edit.getByRole("button", { name: "請求金額を確定する", exact: true })).toBeDisabled();
  await edit.getByLabel("請求月（必須）").fill("2026-11");
  const amount = edit.getByRole("textbox", { name: "通常請求額（インセンティブを除く・税抜・円）", exact: true });
  await amount.fill("２５００００");
  await expect(amount).toHaveValue("250,000");
  const reading = edit.getByText("25万円", { exact: true });
  await expect(reading).toBeVisible();
  const textStart = await reading.evaluate((el) => { const range = document.createRange(); range.selectNodeContents(el); return { x: range.getBoundingClientRect().x, fontSize: parseFloat(getComputedStyle(el).fontSize) }; });
  const inputStart = await amount.evaluate((el) => el.getBoundingClientRect().x + parseFloat(getComputedStyle(el).paddingLeft) + parseFloat(getComputedStyle(el).borderLeftWidth));
  expect(Math.abs(textStart.x - inputStart)).toBeLessThan(1);
  expect(textStart.fontSize).toBeGreaterThanOrEqual(16);
  await page.screenshot({ path: testInfo.outputPath("grouped-billing-amount.png") });
  await amount.press("Home");
  await amount.press("ArrowRight");
  await amount.press("1");
  await expect(amount).toHaveValue("2,150,000");
  await expect(edit.getByText("215万円", { exact: true })).toBeVisible();
  await amount.fill("10001");
  await edit.getByRole("button", { name: "請求金額を確定する", exact: true }).click();
  await expect(edit).toHaveCount(0);
  await expect(page.getByRole("link", { name: "依頼書の金額確定 未入力0件" }).locator(".nav-unread-badge")).toHaveCount(0);
  expect(state.writes[0].body).toMatchObject({ amount: "10001", billing_month: "202611", expected_revision: 0, incentive_amount: null });
  expect(state.writes[0].body).not.toHaveProperty("client_id");
  await page.getByLabel("請求月", { exact: true }).fill("2026-11");
  await page.getByRole("button", { name: "月次請求書を作成", exact: true }).click();
  expect(state.writes).toHaveLength(1);
  const create = page.getByRole("dialog", { name: "依頼元別の月次請求書を作成", exact: true });
  await create.getByRole("combobox", { name: "請求先", exact: true }).selectOption("c1");
  await create.getByLabel("請求日", { exact: true }).fill("2026-11-30");
  await create.getByRole("button", { name: "請求書の下書きを作成", exact: true }).click();
  const detail = page.getByRole("dialog", { name: "月次請求書の確認", exact: true });
  await expect(detail).toContainText("￥11,001");
  await page.screenshot({ path: testInfo.outputPath("monthly-invoice-draft.png") });
  await detail.getByRole("button", { name: "確認して発行する", exact: true }).click();
  await page.getByRole("dialog", { name: "月次請求書を発行", exact: true }).getByRole("button", { name: "確認して発行する", exact: true }).click();
  await expect(detail).toContainText("発行済み");
  await expect(detail.getByRole("button", { name: "下書きを取り消す" })).toHaveCount(0);
});

test("stale amount preserves input and reports conflict", async ({ page }) => {
  await mocks(page, "admin", true);
  await page.goto("/billing/order-amounts");
  await page.getByRole("button", { name: "請求金額を確定", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "依頼書の請求金額を確定", exact: true });
  await edit.getByLabel("請求月（必須）").fill("2026-11");
  const amount = edit.getByRole("textbox", { name: "通常請求額（インセンティブを除く・税抜・円）", exact: true });
  await amount.fill("10001");
  await edit.getByRole("button", { name: "請求金額を確定する", exact: true }).click();
  await expect(edit.getByRole("alert")).toContainText("別の操作で金額が更新");
  await expect(amount).toHaveValue("10,001");
});

test("accounting permissions cannot reveal menu or request billing data", async ({ page }) => {
  const state = await mocks(page, "accounting");
  await page.goto("/billing/order-amounts");
  await expect(page).toHaveURL(/\/403$/);
  await expect(page.getByRole("link", { name: /依頼書の金額確定/ })).toHaveCount(0);
  expect(state.calls).toHaveLength(0);
});

test("issuer settings start with supplied company address and can be edited in a popup", async ({ page }, testInfo) => {
  const state = await mocks(page);
  await page.goto("/billing/order-amounts");
  await page.getByRole("button", { name: "発行元・振込先設定", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "請求書の発行元・振込先設定", exact: true });
  await expect(settings.getByLabel("発行元の正式名称（必須）")).toHaveValue("株式会社VANZAI");
  await expect(settings.getByLabel("郵便番号", { exact: true })).toHaveValue("116-0002");
  await expect(settings.getByRole("textbox", { name: "発行元住所", exact: true })).toHaveValue("東京都荒川区荒川1丁目39-11 東京アルバタワー1703");
  await settings.getByRole("textbox", { name: "振込先（任意）", exact: true }).fill("検証用銀行 検証支店\n普通 1234567 カ）バンザイ");
  await settings.getByRole("textbox", { name: "支払期限・条件（任意）", exact: true }).fill("請求月の翌月末まで");
  await page.screenshot({ path: testInfo.outputPath("issuer-settings.png") });
  await settings.getByRole("button", { name: "設定を保存する" }).click();
  await expect(settings).toHaveCount(0);
  expect(state.writes[0].body).toMatchObject({ expected_revision: 1, name: "株式会社VANZAI", bank_details: "検証用銀行 検証支店\n普通 1234567 カ）バンザイ" });
  await page.getByRole("button", { name: "発行元・振込先設定", exact: true }).click();
  await expect(settings.getByRole("textbox", { name: "支払期限・条件（任意）", exact: true })).toHaveValue("請求月の翌月末まで");
});

test("incentive memo is copied verbatim and pending amount stays in the red badge until zero is confirmed", async ({ page }, testInfo) => {
  const state = await mocks(page, "admin", false, true);
  await page.goto("/billing/order-amounts");
  await page.getByRole("button", { name: "請求金額を確定", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "依頼書の請求金額を確定", exact: true });
  await expect(edit.getByText("販売1台につき500円\n翌月実績確定", { exact: true })).toBeVisible();
  await edit.getByLabel("請求月（必須）").fill("2026-11");
  await edit.getByRole("textbox", { name: "通常請求額（インセンティブを除く・税抜・円）", exact: true }).fill("10001");
  await edit.getByRole("button", { name: "通常請求額を保存（インセンティブ未確定）", exact: true }).click();
  await expect(edit).toHaveCount(0);
  await expect(page.getByRole("link", { name: "依頼書の金額確定 未入力1件", exact: true }).locator(".nav-unread-badge")).toHaveText("1");
  await page.getByRole("button", { name: "金額・請求月を変更", exact: true }).click();
  const incentive = edit.getByRole("textbox", { name: "インセンティブ金額（税抜・円）", exact: true });
  await incentive.fill("２５００．７５");
  await expect(incentive).toHaveValue("2,500.75");
  await expect(edit.getByText("2500.75円", { exact: true })).toBeVisible();
  await incentive.fill("0");
  await expect(edit.getByText("0円", { exact: true })).toBeVisible();
  await edit.getByRole("textbox", { name: "変更理由（必須）", exact: true }).fill("販売実績が0円");
  await page.screenshot({ path: testInfo.outputPath("incentive-amount.png") });
  await edit.getByRole("button", { name: "請求金額を確定する", exact: true }).click();
  await expect(page.getByRole("link", { name: "依頼書の金額確定 未入力0件", exact: true }).locator(".nav-unread-badge")).toHaveCount(0);
  expect(state.writes[1].body.incentive_amount).toBe("0");
});
