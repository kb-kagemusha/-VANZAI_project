import assert from "node:assert/strict";
import test from "node:test";

import { workerEditFieldsFromGuard } from "./workerEditForm.ts";

test("保存後は、別管理者の電話を古い入力のまま再保存しない", () => {
  const stalePhone = "08000000000";
  const fresh = {
    edit_guard: "ticket-after-other-admin",
    worker: {
      id: "worker-1",
      name: "自分の保存",
      furigana: null,
      email: "kept@example.com",
      phone: "09011112222",
      sole_proprietor_name: null,
      emergency_contact_name_kana: null,
      emergency_contact_phone: null,
      gender: null,
      invoice_registration_status: null,
      invoice_number: null,
      is_active: true,
      introducer_supplier_id: null,
      introducer_supplier_name: null,
      notes: null,
      smoking_area_ok: null,
      has_p_shirt: null,
      has_best: null,
      stores_training_done: null,
      pioneer_training_done: null,
      p_shirt_count: null,
      license_type: null,
      tags: [],
    },
  };

  const fields = workerEditFieldsFromGuard(fresh);
  const nextSave = { phone: stalePhone, name: "画面に残った氏名", ...fields };

  assert.equal(nextSave.phone, "09011112222");
  assert.notEqual(nextSave.phone, stalePhone);
  assert.equal(nextSave.name, fresh.worker.name);
  assert.equal(fresh.edit_guard, "ticket-after-other-admin");
});
