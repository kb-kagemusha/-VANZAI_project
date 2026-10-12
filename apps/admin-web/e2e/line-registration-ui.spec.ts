import { test, expect, type Page } from "@playwright/test";

async function setup(page: Page, options: { linked?: boolean; expireOnce?: boolean; notSaved?: boolean; differentPerson?: boolean } = {}) {
  const submitted: Array<{ key: string; body: Record<string, string>; token: string }> = [];
  let sessions = 0;
  await page.addInitScript(() => {
    (window as any).liff = { init: async () => {}, isLoggedIn: () => true, login: () => {}, getIDToken: () => "mock-id-token" };
  });
  await page.route("**/api/line/registration/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const response = (json: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(json) });
    if (path.endsWith("/entry")) return response({ enabled: true, liff_id: "test-only" });
    if (path.endsWith("/sessions")) {
      sessions += 1;
      return response({ token: `token-${sessions}`, linked: Boolean(options.linked), subject_tag: options.differentPerson && sessions > 1 ? "other-person" : "same-person", expires_at: "2099-01-01" });
    }
    if (path.endsWith("/form")) return response({ linked: Boolean(options.linked), pending: false, message: "" });
    if (path.endsWith("/submissions")) {
      submitted.push({ key: route.request().headers()["idempotency-key"], body: route.request().postDataJSON(), token: route.request().headers().authorization });
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
  for (const [key, value] of Object.entries({ last_name: "山田", first_name: "太郎", last_name_furigana: "やまだ", first_name_furigana: "たろう", phone: "09000001111", birth_date: "1990-01-02", postal_code: "1000001", address1: "千代田区1-1", nearest_station: "新宿駅", station_walk_minutes: "0" })) {
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
