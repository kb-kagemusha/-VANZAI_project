import { expect, test, type Page } from "@playwright/test";

const person = { name: "運営テスト", phone: "09011112222", permissions: { wake: true, orders: true, availability: true } };
async function setup(page: Page) {
  await page.route("https://static.line-scdn.net/liff/edge/2/sdk.js", (route) => route.fulfill({ contentType: "application/javascript", body: "window.liff={init:async()=>{},isLoggedIn:()=>true,login:()=>{},getIDToken:()=> 'proof'};" }));
  await page.route("**/api/line/operator-registration/entry", (route) => route.fulfill({ json: { enabled: true, liff_id: "2011980694-test" } }));
  await page.route("**/api/line/operator/session", (route) => route.fulfill({ json: { token: "operator-token" } }));
  await page.route("**/api/line/operator/me", (route) => route.fulfill({ json: person }));
  await page.route("**/api/line/operator/wake-status?*", (route) => route.fulfill({ json: { date: "2026-10-26", total: 2, reported: 1, items: [
    { worker_id: "w1", worker_name: "未報告テスト", first_start: "09:00", wake_reported_at: null, next_action: {step: "wait", label: "報告待ち", priority: 1}, handler: null, last_result: null, entries: [{ project_name: "駅前イベント", site_name: "会場A", start_time: "09:00", end_time: "18:00", status: "active" }] },
    { worker_id: "w2", worker_name: "報告済テスト", first_start: "10:00", wake_reported_at: "2026-10-26T00:00:00Z", next_action: {step: "resolved", label: "報告済み", priority: 0}, handler: null, last_result: null, entries: [] },
  ] } }));
  await page.route("**/api/line/operator/calendar?*", (route) => {
    const url = new URL(route.request().url());
    const date = url.searchParams.get("start")!;
    return route.fulfill({ json: url.searchParams.get("kind") === "orders" ? { kind: "orders", days: [{ date, events: [{ version_id: "v1", document_number: "ORD-1", project_name: "全案件テスト", site_name: "会場A", ok: [{ worker_id: "w1", name: "参加者テスト" }], changing: [], unanswered: [], unavailable: [] }] }] } : { kind: "availability", workers: [{ worker_id: "w2", name: "全稼働者テスト", days: { [date]: { status: "available_all_day", assignments: [] } } }] } });
  });
}

test("mobile operator can read wake, calendar and own profile without admin login", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await page.goto("/public/line-operator-registration?m=wake");
  await expect(page.getByRole("heading", { name: "未報告テスト" })).toBeVisible();
  await expect(page.getByText("未報告", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("button", { name: "案件カレンダー", exact: true }).click();
  await page.getByRole("button", { name: "1日", exact: true }).click();
  await expect(page.getByRole("heading", { name: "全案件テスト" })).toBeVisible();
  await page.getByRole("button", { name: "出勤可否・配置", exact: true }).click();
  await expect(page.getByRole("heading", { name: "全稼働者テスト" })).toBeVisible();
  await page.screenshot({ path: "../../.work/operator-availability-mobile.png", fullPage: true });
  await page.goto("/public/line-operator-registration?m=profile");
  await expect(page.getByText("09011112222", { exact: true })).toBeVisible();
});

test("permission rejection clears previously fetched business information", async ({ page }) => {
  await setup(page);
  await page.goto("/public/line-operator-registration?m=wake");
  await expect(page.getByRole("heading", { name: "未報告テスト" })).toBeVisible();
  await page.route("**/api/line/operator/wake-status?*", (route) => route.fulfill({ status: 403, json: { detail: "権限が変更されました" } }));
  await page.getByRole("button", { name: "最新の状況に更新" }).click();
  await expect(page.getByRole("alert")).toContainText("権限が変更されました");
  await expect(page.getByRole("heading", { name: "未報告テスト" })).toHaveCount(0);
});

test("LIFF redirect state selects portal before invitation validation", async ({ page }) => {
  await setup(page);
  await page.goto("/public/line-operator-registration?liff.state=%3Fm%3Dprofile");
  await expect(page.getByRole("heading", { name: "自分の登録情報" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

for (const width of [360, 390, 1280]) {
  for (const theme of ["light", "dark"]) {
    test(`operator layout ${width}px ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await setup(page);
      await page.goto("/public/line-operator-registration?m=wake");
      await expect(page.getByRole("heading", { name: "未報告テスト" })).toBeVisible();
      await page.evaluate((theme) => document.documentElement.dataset.theme = theme, theme);
      await expect(page.getByRole("img", { name: "VANZAI", exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await expect(page.locator(".operator-container")).toHaveCSS("max-width", "560px");
      await page.screenshot({ path: `../../.work/operator-${width}-${theme}.png`, fullPage: true });
    });
  }
}
