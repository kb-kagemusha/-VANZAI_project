import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, options: { workerConflict?: boolean; profileRefreshFailure?: boolean; places?: boolean } = {}) {
  const writes: { path: string; body: any }[] = [];
  let staff: any[] = [];
  let updatedWorker = false;
  const worker = { id: "test-worker", name: "試験 太郎", furigana: "しけん たろう", is_active: true, tags: [], profile: null };
  let savedVersion: any;
  await page.addInitScript(() => { localStorage.setItem("vanzai.admin.access_token", "mock-token"); });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    const respond = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me")) return respond({ id: "mock-admin", username: "mock-admin", display_name: "試験管理者", role: "admin", is_active: true });
    if (path.endsWith("/auth/session")) return respond({ access_token: "mock-token", refresh_token: "mock-refresh", token_type: "bearer" });
    const method = route.request().method();
    if (path === "/api/workers") return respond({ items: [worker], total: 1, offset: 0, limit: 30 });
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
      return respond(savedVersion);
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
  await page.getByLabel("勤務条件1の開始日").fill("2027-03-01");
  const first = page.getByRole("group", { name: "勤務条件 1", exact: true });
  await first.getByLabel("開始時間").fill("08:00"); await first.getByLabel("終了時間").fill("17:00");
  await first.getByLabel("勤務の備考").fill("初日準備");
  await page.getByRole("button", { name: "稼働日・期間を追加" }).click();
  await page.getByLabel("勤務条件2の日付の設定").selectOption("range");
  await page.getByLabel("勤務条件2の開始日").fill("2027-03-02"); await page.getByLabel("勤務条件2の終了日").fill("2027-03-10");
  const second = page.getByRole("group", { name: "勤務条件 2", exact: true });
  await second.getByLabel("開始時間").fill("09:00"); await second.getByLabel("終了時間").fill("17:00");
  await expect(page.getByRole("checkbox", { name: "稼働日の設定で単価設定する" })).toBeChecked();
  const rates = page.locator("fieldset").filter({ has: page.getByLabel("単価（円・税抜）") });
  await rates.nth(0).getByLabel("単価（円・税抜）").fill("20500");
  await rates.nth(1).getByLabel("単価（円・税抜）").fill("19500");
  await expect(rates.nth(0).getByLabel("昼食代：込み")).toBeChecked(); await expect(rates.nth(0).getByLabel("交通費：込み")).toBeChecked();
  await rates.nth(1).getByLabel("交通費：込み").uncheck(); await rates.nth(1).getByLabel("交通費の備考").fill("実費上限1,000円");
  await first.screenshot({ path: "../../artifacts/order-date-groups.png" });
  await page.getByLabel("所在地の登録住所").fill("主催者確認住所");
  await page.getByLabel(/^期限の案内/).fill("2027-02-20");
  await page.getByRole("button", { name: "下書きを保存", exact: true }).click();
  await expect(page.getByText("下書きを保存しました。確定するまで送付は始まりません。")).toBeVisible();
  const payload = writes.find((w) => w.path === "/api/order-requests")!.body;
  const schedule = JSON.parse(payload.request_conditions).schedule;
  expect(schedule.work_groups).toHaveLength(2); expect(schedule.rate_groups).toHaveLength(2);
  expect(schedule.rate_groups[1].from).toBe("2027-03-02"); expect(schedule.rate_groups[1].to).toBe("2027-03-10");
  expect(payload.body).toContain("¥20,500"); expect(payload.body).toContain("交通費：別途（実費上限1,000円）"); expect(payload.body).toContain("主催者確認住所");
});

test("date conditions and operator editor fit a mobile screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page); await page.goto("/operations/order-requests");
  await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByRole("group", { name: "勤務条件 1", exact: true }).scrollIntoViewIfNeeded();
  expect(await page.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.goto("/masters/operator-staff"); await page.getByRole("button", { name: "運営スタッフを登録" }).click();
  expect(await page.locator(".order-draft-body").evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.getByRole("dialog", { name: "運営スタッフ登録" }).getByRole("button", { name: "閉じる" }).click();
  await expect(page.getByRole("dialog", { name: "運営スタッフ登録" })).toHaveCount(0);
});

test("Google place selection stores ID while address remains user supplied and venue edits clear stale ID", async ({ page }) => {
  await setup(page, { places: true }); await page.goto("/operations/order-requests"); await page.getByRole("button", { name: "新規の依頼書を作成" }).click();
  await page.getByRole("textbox", { name: "稼働場所", exact: true }).fill("横浜赤レンガ倉庫 イベント広場");
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
