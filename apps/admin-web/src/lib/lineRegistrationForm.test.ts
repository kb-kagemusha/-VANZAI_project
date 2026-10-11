import assert from "node:assert/strict";
import test from "node:test";

import {
  emptyLineRegistrationInput,
  idempotencyKeyAfterAttempt,
  lineRegistrationPayload,
  screenAfterReauthentication,
  screenAfterUnauthorized,
} from "./lineRegistrationForm.ts";

test("期限切れのあと同じ本人で確認し直すと、入力と新しい受付を残す", () => {
  const typed = { ...emptyLineRegistrationInput(), last_name: "山田", phone: "09000001111" };
  const open = {
    input: typed,
    token: "expired-token",
    subject: "tag-a",
    linked: false,
    needsReauth: false,
    error: "",
    message: "",
  };
  const failed = screenAfterUnauthorized(open, "本人確認の期限が切れました。");
  assert.equal(failed.needsReauth, true);
  assert.equal(failed.input.last_name, "山田");
  assert.equal(failed.input.phone, "09000001111");
  assert.equal(failed.token, "expired-token");

  const renewed = screenAfterReauthentication(failed, {
    token: "fresh-token",
    subject: "tag-a",
    linked: true,
  });
  assert.equal(renewed.needsReauth, false);
  assert.equal(renewed.token, "fresh-token");
  assert.equal(renewed.input.phone, "09000001111");
  assert.equal(renewed.message, "本人確認をやり直しました。もう一度送信してください。");

  const otherPerson = screenAfterReauthentication(failed, {
    token: "other-token",
    subject: "tag-b",
    linked: false,
  });
  assert.equal(otherPerson.input.last_name, "");
  assert.equal(otherPerson.input.phone, "");
  assert.equal(otherPerson.error, "別のLINEアカウントになったため、入力を消しました。");
});

test("通信失敗の再送だけ、同じ送信識別子を使う", () => {
  assert.equal(idempotencyKeyAfterAttempt("key-1", "network"), "key-1");
  assert.equal(idempotencyKeyAfterAttempt("key-1", 503), "key-1");
  assert.equal(idempotencyKeyAfterAttempt("key-1", 409), "");
  assert.equal(idempotencyKeyAfterAttempt("key-1", 401), "");
});

test("紐付け済みの空欄は送らず、住所は空の建物名も送る", () => {
  const input = {
    ...emptyLineRegistrationInput(),
    phone: "09000001111",
    postal_code: "1000001",
    prefecture: "東京都",
    address1: "千代田区1-1",
  };
  const payload = lineRegistrationPayload(input, true);
  assert.deepEqual(payload, {
    phone: "09000001111",
    postal_code: "1000001",
    prefecture: "東京都",
    address1: "千代田区1-1",
    address2: "",
  });
});
