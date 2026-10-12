import assert from "node:assert/strict";
import test from "node:test";
import { normalizePostalCode, lookupPostalAddress } from "./postalAddress.ts";

test("郵便番号のハイフンと全角数字を入力時に整える", () => {
  assert.equal(normalizePostalCode("１００－０００１"), "1000001");
  assert.equal(normalizePostalCode("100-0001"), "1000001");
});

test("住所検索には郵便番号だけを送り、違う郵便番号の結果は使わない", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(String(url), "https://zipcloud.ibsnet.co.jp/api/search?zipcode=1000001");
      assert.equal(options?.credentials, "omit");
      assert.equal(options?.referrerPolicy, "no-referrer");
      return new Response(JSON.stringify({ status: 200, results: [
        { zipcode: "1000001", address1: "東京都", address2: "千代田区", address3: "千代田" },
        { zipcode: "9999999", address1: "東京都", address2: "誤った町", address3: "" },
      ] }), { status: 200 });
    };
    assert.deepEqual(await lookupPostalAddress("1000001", new AbortController().signal), [{ prefecture: "東京都", address: "千代田区千代田" }]);
  } finally { globalThis.fetch = original; }
});
