import assert from "node:assert/strict";
import test from "node:test";

import {
  emptyLineRegistrationInput,
  idempotencyKeyAfterAttempt,
  lineRegistrationPayload,
  registrationInputAfterSubjectChange,
} from "./lineRegistrationForm.ts";

test("別のLINE本人になったときは、前の入力を送らない", () => {
  const current = { ...emptyLineRegistrationInput(), last_name: "前の人" };
  const cleared = registrationInputAfterSubjectChange("subject-a", "subject-b", current);
  assert.equal(cleared.last_name, "");
  const kept = registrationInputAfterSubjectChange("", "subject-b", current);
  assert.equal(kept.last_name, "前の人");
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
