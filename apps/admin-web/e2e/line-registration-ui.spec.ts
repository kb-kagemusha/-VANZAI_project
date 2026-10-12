import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, options: { linked?: boolean; expireOnce?: boolean; notSaved?: boolean; differentPerson?: boolean; registered?: Record<string, string> } = {}) {
  const submitted: Array<{ key: string; body: Record<string, string>; token: string; ticket?: string }> = [];
  let sessions = 0;
  await page.addInitScript(() => {
    (window as any).liff = { init: async () => {}, isLoggedIn: () => true, login: () => {}, getIDToken: () => "mock-id-token" };
  });
  await page.route("https://zipcloud.ibsnet.co.jp/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: 200, results: [{ zipcode: "1000001", address1: "東京都", address2: "千代田区", address3: "千代田" }] }) }));
  await page.route("**/api/line/registration/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const response = (json: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(json) });
    if (path.endsWith("/entry")) return response({ enabled: true, liff_id: "test-only" });
    if (path.endsWith("/sessions")) {
      sessions += 1;
      return response({ token: `token-${sessions}`, linked: Boolean(options.linked), subject_tag: options.differentPerson && sessions > 1 ? "other-person" : "same-person", expires_at: "2099-01-01" });
    }
    if (path.endsWith("/form")) {
      const changed = options.differentPerson && sessions > 1;
      const registered = options.registered ? { ...options.registered, ...(changed ? { last_name: "別", first_name: "本人", phone: "09000009999" } : {}) } : undefined;
      return response({ linked: Boolean(options.linked), registered, target_tag: registered ? (changed ? "other-target" : "original-target") : undefined, form_ticket: registered ? (changed ? "other-ticket" : "original-ticket") : undefined, pending: false, message: "" });
    }
    if (path.endsWith("/submissions")) {
      submitted.push({ key: route.request().headers()["idempotency-key"], body: route.request().postDataJSON(), token: route.request().headers().authorization, ticket: route.request().headers()["x-registration-form-ticket"] });
      if (options.expireOnce && submitted.length === 1) return response({ detail: "本人確認の期限が切れました。入力は残しています。" }, 401);
      return response({ request_id: "test-request", status: "pending", saved: !options.notSaved, message: options.notSaved ? "今回入力した内容は申請本文に保存していません" : "受付済みです。管理者が確認します。" });
    }
    throw new Error(`Unexpected registration route: ${path}`);
  });
  await page.goto("/public/line-registration");
  await expect(page.locator("#lr-last_name")).toBeVisible();
  return submitted;
}

test("mobile layout, logo and purpose are shown before input", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await setup(page);
  await expect(page).toHaveTitle("稼働者登録｜VANZAI");
  await expect(page.getByAltText("VANZAI ロゴ")).toBeVisible();
  await expect(page.getByText(/これらの目的以外には利用しません/)).toBeVisible();
  await expect(page.getByText("最寄り駅", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator("#lr-phone").evaluate((element) => getComputedStyle(element).fontSize)).toBe("16px");
  await page.screenshot({ path: "../../artifacts/line-registration-mobile.png", fullPage: false });
  expect(errors).toEqual([]);
});

test("validate then confirm before sending optional station information", async ({ page }) => {
  const submitted = await setup(page);
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await expect(page.getByText("電話番号を入力してください", { exact: true })).toBeVisible();
  expect(submitted).toHaveLength(0);
  for (const [key, value] of Object.entries({ last_name: "山田", first_name: "太郎", last_name_furigana: "やまだ", first_name_furigana: "たろう", phone: "09000001111", email: "worker@example.com", birth_date: "1990-01-02", postal_code: "1000001", address1: "千代田区1-1", nearest_station: "新宿駅", station_walk_minutes: "0", emergency_contact_phone: "09000002222", emergency_contact_name: "山田 花子", emergency_contact_relationship: "実母" })) {
    await page.locator(`#lr-${key}`).fill(value);
  }
  await page.locator("#lr-prefecture").selectOption("東京都");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await expect(page.getByText("徒歩0分", { exact: true })).toBeVisible();
  expect(submitted).toHaveLength(0);
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toBeVisible();
  expect(submitted[0].body.nearest_station).toBe("新宿駅");
  expect(submitted[0].body.station_walk_minutes).toBe("0");
  expect(submitted[0].body.emergency_contact_relationship).toBe("実母");
});

test("same person reauth keeps the exact operation and station input", async ({ page }) => {
  const submitted = await setup(page, { linked: true, expireOnce: true });
  await page.locator("#lr-nearest_station").fill("新宿駅");
  await page.locator("#lr-station_walk_minutes").fill("0");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await page.getByRole("button", { name: "本人確認をやり直す" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toBeVisible();
  expect(submitted).toHaveLength(2);
  expect(submitted[1].key).toBe(submitted[0].key);
  expect(submitted[1].body).toEqual(submitted[0].body);
  expect(submitted[1].token).not.toBe(submitted[0].token);
});

test("not saved does not show a new receipt", async ({ page }) => {
  await setup(page, { linked: true, notSaved: true });
  await page.locator("#lr-station_walk_minutes").fill("10");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("heading", { name: "前回の申請を確認中です" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toHaveCount(0);
});

test("different LINE person clears the input after reauth", async ({ page }) => {
  const submitted = await setup(page, { linked: true, expireOnce: true, differentPerson: true });
  await page.locator("#lr-nearest_station").fill("新宿駅");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await page.getByRole("button", { name: "本人確認をやり直す" }).click();
  await expect(page.locator("#lr-nearest_station")).toHaveValue("");
  expect(submitted).toHaveLength(1);
});

test("postcode fills the address and building stays unchanged", async ({ page }) => {
  await setup(page, { linked: true });
  await page.locator("#lr-address2").fill("ビル101号室");
  await page.locator("#lr-postal_code").fill("100-0001");
  await expect(page.locator("#lr-postal_code")).toHaveValue("1000001");
  await expect(page.locator("#lr-prefecture")).toHaveValue("東京都");
  await expect(page.locator("#lr-address1")).toHaveValue("千代田区千代田");
  await expect(page.locator("#lr-address2")).toHaveValue("ビル101号室");
  await expect(page.getByText("住所を入力しました。続けて番地を入力してください。")).toBeVisible();
});

test("a slow lookup does not overwrite a manually edited address", async ({ page }) => {
  await setup(page, { linked: true });
  let release: () => void = () => {};
  let started = false;
  await page.route("https://zipcloud.ibsnet.co.jp/**", async (route) => {
    started = true;
    await new Promise<void>((resolve) => { release = resolve; });
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: 200, results: [{ zipcode: "1000001", address1: "東京都", address2: "千代田区", address3: "千代田" }] }) });
  });
  await page.locator("#lr-postal_code").fill("1000001");
  await expect.poll(() => started).toBe(true);
  await page.locator("#lr-prefecture").selectOption("東京都");
  await page.locator("#lr-address1").fill("手入力した住所1-2");
  release();
  await expect(page.getByText(/手入力した住所を残しました/)).toBeVisible();
  await expect(page.locator("#lr-address1")).toHaveValue("手入力した住所1-2");
});

test("ambiguous postcode requires choosing an address", async ({ page }) => {
  await setup(page, { linked: true });
  await page.route("https://zipcloud.ibsnet.co.jp/**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: 200, results: ["町A", "町B"].map((town) => ({ zipcode: "1000001", address1: "東京都", address2: "千代田区", address3: town })) }) }));
  await page.locator("#lr-postal_code").fill("1000001");
  await expect(page.locator("#lr-address1")).toHaveValue("");
  await page.getByRole("combobox", { name: "郵便番号の住所候補" }).selectOption("1");
  await expect(page.locator("#lr-address1")).toHaveValue("千代田区町B");
});

test("lookup failure permits manual entry", async ({ page }) => {
  await setup(page, { linked: true });
  await page.route("https://zipcloud.ibsnet.co.jp/**", (route) => route.fulfill({ status: 500 }));
  await page.locator("#lr-postal_code").fill("1000001");
  await expect(page.getByText(/手入力で続けられます/)).toBeVisible();
  await page.locator("#lr-prefecture").selectOption("東京都");
  await page.locator("#lr-address1").fill("千代田区1-1");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await expect(page.getByRole("heading", { name: "入力内容をご確認ください" })).toBeVisible();
});

test("new registration requires everything except the building", async ({ page }) => {
  await setup(page);
  await expect(page.locator("#lr-email")).toHaveAttribute("aria-required", "true");
  await expect(page.locator("#lr-nearest_station")).toHaveAttribute("aria-required", "true");
  await expect(page.locator("#lr-emergency_contact_relationship")).toHaveAttribute("aria-required", "true");
  await expect(page.locator("#lr-address2")).toHaveAttribute("aria-required", "false");
});

test("worker list new registration saves the same emergency fields", async ({ page }) => {
  let created: Record<string, string> | undefined;
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-admin-token"));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return respond({ id: "test-admin", username: "test-admin", display_name: "試験管理者", email: "test@example.com", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-admin-token", refresh_token: "mock-refresh-token", token_type: "bearer" });
    if (path === "/api/workers" && route.request().method() === "POST") {
      created = route.request().postDataJSON();
      return respond({ ...created, id: "test-worker" });
    }
    return respond({ items: [], total: 0, offset: 0, limit: 20 });
  });
  await page.goto("/masters/workers");
  await page.getByRole("button", { name: "新規登録", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("姓", { exact: false }).first().fill("架空");
  await dialog.getByLabel(/^名/).first().fill("稼働者");
  await dialog.getByLabel("姓ふりがな", { exact: false }).fill("かくう");
  await dialog.getByLabel("名ふりがな", { exact: false }).fill("かどうしゃ");
  await dialog.getByLabel("緊急連絡先の電話番号", { exact: false }).fill("09000002222");
  await dialog.getByLabel("緊急連絡先のお名前", { exact: false }).fill("架空の連絡先");
  await dialog.getByLabel("ご本人との関係", { exact: false }).fill("実父");
  await dialog.getByRole("button", { name: "登録する", exact: true }).click();
  await expect.poll(() => created?.emergency_contact_relationship).toBe("実父");
  expect(created?.emergency_contact_phone).toBe("09000002222");
  expect(created?.emergency_contact_name).toBe("架空の連絡先");
});

const registeredWorker = { last_name: "山田", first_name: "太郎", last_name_furigana: "やまだ", first_name_furigana: "たろう", phone: "09000001111", email: "worker@example.com", birth_date: "1990-01-02", postal_code: "1000001", prefecture: "東京都", address1: "千代田区1-1", address2: "", nearest_station: "新宿駅", station_walk_minutes: "0", emergency_contact_phone: "09000002222", emergency_contact_name: "架空の連絡先", emergency_contact_relationship: "実母" };

test("linked prefill marks missing email required and sends only the completed value", async ({ page }) => {
  const submitted = await setup(page, { linked: true, registered: { ...registeredWorker, email: "" } });
  await expect(page.locator("#lr-first_name")).toHaveValue("太郎");
  await expect(page.locator('label[for="lr-email"]')).toContainText("必須");
  await expect(page.locator('label[for="lr-phone"]')).toContainText("登録済み");
  await page.locator("#lr-email").fill("completed@example.com");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toBeVisible();
  expect(submitted[0].body).toEqual({ email: "completed@example.com" });
  expect(submitted[0].ticket).toBe("original-ticket");
});

test("different linked person reloads their saved information and ticket after reauth", async ({ page }) => {
  const submitted = await setup(page, { linked: true, registered: registeredWorker, expireOnce: true, differentPerson: true });
  await page.locator("#lr-phone").fill("09000007777");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await page.getByRole("button", { name: "本人確認をやり直す" }).click();
  await expect(page.locator("#lr-last_name")).toHaveValue("別");
  await expect(page.locator("#lr-phone")).toHaveValue("09000009999");
  await page.locator("#lr-phone").fill("09000008888");
  await page.getByRole("button", { name: "入力内容を確認する" }).click();
  await page.getByRole("button", { name: "この内容で申請する" }).click();
  await expect(page.getByRole("heading", { name: "申請を受け付けました" })).toBeVisible();
  expect(submitted[1].ticket).toBe("other-ticket");
  expect(submitted[1].key).not.toBe(submitted[0].key);
  expect(submitted[1].body).toEqual({ phone: "09000008888" });
});

test("closing panel disables self approval and confirms another person's request", async ({ page }) => {
  let approved = "";
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token", "mock-admin-token"));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (json: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(json) });
    if (path.endsWith("/auth/me")) return respond({ id: "test-admin", username: "test-admin", email: "test@example.com", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-admin-token", refresh_token: "mock-refresh-token", token_type: "bearer" });
    if (path === "/api/dashboard") return respond({ unprocessed_items: [], variance_alerts: [], closing_status: [] });
    if (path.endsWith("/approve")) { approved = "other"; return respond({ status: "open" }); }
    if (path === "/api/closing/approvals") return respond({ items: approved ? [] : [
      { id: "mine", project_name: "本人の申請", period_key: "202610", action: "soft_release", requested_by: "test-admin", reason: "再確認", expires_at: "2099-01-01", can_approve: false },
      { id: "other", project_name: "別の人の申請", period_key: "202610", action: "soft_release", requested_by: "another-admin", reason: "実績修正", expires_at: "2099-01-01", can_approve: true },
    ] });
    return respond({ items: [], total: 0, offset: 0, limit: 20 });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "締めの承認待ち" })).toBeVisible();
  const buttons = page.getByRole("button", { name: "承認する", exact: true });
  await expect(buttons.nth(0)).toBeDisabled();
  await buttons.nth(1).click();
  await page.getByRole("dialog").getByRole("button", { name: "承認する", exact: true }).click();
  await expect.poll(() => approved).toBe("other");
});
