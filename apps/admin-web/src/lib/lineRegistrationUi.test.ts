import assert from "node:assert/strict";
import test from "node:test";
import { emptyLineRegistrationInput, lineRegistrationPayload } from "./lineRegistrationForm.ts";
import { PREFECTURES, validateRegistrationInput } from "./lineRegistrationUi.ts";

test("任意の駅情報だけでも更新でき、徒歩0分は空欄扱いにしない", () => {
  const input = { ...emptyLineRegistrationInput(), station_walk_minutes: "0" };
  assert.deepEqual(validateRegistrationInput(input, true), {});
  assert.deepEqual(lineRegistrationPayload(input, true), { station_walk_minutes: "0" });
  assert.equal(PREFECTURES.length, 47);
});

test("新規の必須項目と、部分更新の氏名・住所の組を案内する", () => {
  const errors = validateRegistrationInput(emptyLineRegistrationInput(), false);
  assert.ok(errors.last_name && errors.phone && errors.birth_date && errors.postal_code);
  assert.ok(errors.email && errors.nearest_station && errors.station_walk_minutes && errors.emergency_contact_phone);
  assert.equal(errors.address2, undefined);
  const partial = validateRegistrationInput({ ...emptyLineRegistrationInput(), last_name: "山田", address2: "建物" }, true);
  assert.ok(partial.first_name && partial.postal_code && partial.address1);
});

test("不正な徒歩時間と未来・実在しない生年月日を送信前に止める", () => {
  for (const value of ["-1", "301", "1.5"]) assert.ok(validateRegistrationInput({ ...emptyLineRegistrationInput(), station_walk_minutes: value }, true).station_walk_minutes);
  for (const value of ["2025-02-29", "2099-01-01"]) assert.ok(validateRegistrationInput({ ...emptyLineRegistrationInput(), birth_date: value }, true, "2026-10-12").birth_date);
});
