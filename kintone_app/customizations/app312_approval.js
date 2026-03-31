(function () {
  'use strict';

  const GUEST_SPACE_ID = 3;

  const FIELDS = {
    workerId: 'worker_id',
    isActive: 'is_active',
    group: 'group',
    introducer: 'introducer_supplier',
    lastName: 'last_name',
    firstName: 'first_name',
    lastNameFurigana: 'lastname_furigana',
    firstNameFurigana: 'firstname_furigana',
    phone: 'phone'
  };

  const APPROVE_ACTION_LABEL = '承諾';

  function normalizeText(value) {
    return String(value || '')
      .replace(/[\s\u3000]+/g, '')
      .trim();
  }

  function normalizePhone(value) {
    return String(value || '').replace(/[^\d]/g, '');
  }

  function toValue(record, code) {
    return record && record[code] && typeof record[code].value !== 'undefined'
      ? String(record[code].value || '')
      : '';
  }

  function fetchNextWorkerId() {
    const query = `${FIELDS.workerId} like "WRK%" order by ${FIELDS.workerId} desc limit 1`;
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: kintone.app.getId(),
      query,
      fields: [FIELDS.workerId]
    }).then((resp) => {
      const records = resp.records || [];
      if (records.length === 0) {
        return 'WRK0001';
      }
      const last = toValue(records[0], FIELDS.workerId);
      const suffix = Number(last.replace('WRK', '')) || 0;
      return `WRK${String(suffix + 1).padStart(4, '0')}`;
    });
  }

  function checkDuplicate(record, recordId) {
    const keyLast = normalizeText(toValue(record, FIELDS.lastName));
    const keyFirst = normalizeText(toValue(record, FIELDS.firstName));
    const keyLastKana = normalizeText(toValue(record, FIELDS.lastNameFurigana));
    const keyFirstKana = normalizeText(toValue(record, FIELDS.firstNameFurigana));
    const keyPhone = normalizePhone(toValue(record, FIELDS.phone));

    if (!keyLast || !keyFirst || !keyPhone) {
      return Promise.resolve(false);
    }

    const query = [
      `${FIELDS.lastName} = "${toValue(record, FIELDS.lastName)}"`,
      `${FIELDS.firstName} = "${toValue(record, FIELDS.firstName)}"`,
      `${FIELDS.phone} = "${toValue(record, FIELDS.phone)}"`,
      `$id != "${recordId}"`,
      'limit 1'
    ].join(' and ');

    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: kintone.app.getId(),
      query,
      fields: [FIELDS.lastName, FIELDS.firstName, FIELDS.lastNameFurigana, FIELDS.firstNameFurigana, FIELDS.phone]
    }).then((resp) => {
      const hit = (resp.records || [])[0];
      if (!hit) {
        return false;
      }
      const hitLast = normalizeText(toValue(hit, FIELDS.lastName));
      const hitFirst = normalizeText(toValue(hit, FIELDS.firstName));
      const hitLastKana = normalizeText(toValue(hit, FIELDS.lastNameFurigana));
      const hitFirstKana = normalizeText(toValue(hit, FIELDS.firstNameFurigana));
      const hitPhone = normalizePhone(toValue(hit, FIELDS.phone));
      return (
        keyLast === hitLast &&
        keyFirst === hitFirst &&
        keyLastKana === hitLastKana &&
        keyFirstKana === hitFirstKana &&
        keyPhone === hitPhone
      );
    });
  }

  kintone.events.on('app.record.detail.process.proceed', function (event) {
    const actionLabel = event.action && (event.action.value || event.action.name || event.action);
    if (actionLabel !== APPROVE_ACTION_LABEL) {
      return event;
    }

    const record = event.record;
    const recordId = event.recordId;

    return checkDuplicate(record, recordId).then((isDuplicate) => {
      if (isDuplicate) {
        event.error = '重複候補が見つかりました（氏名+フリガナ+電話）。確認後に承諾してください。';
        return event;
      }

      const currentGroup = toValue(record, FIELDS.group);
      const currentIntroducer = toValue(record, FIELDS.introducer);

      const groupInput = window.prompt('経由先を入力してください（例: VANZAI社直契約 / 紹介者経由 / 下請け経由）', currentGroup || '');
      if (!groupInput || !String(groupInput).trim()) {
        event.error = '経由先は必須です。';
        return event;
      }

      const groupNormalized = String(groupInput).trim().toUpperCase();
      const isVanzaiDirect = groupNormalized === 'VANZAI' || groupNormalized.includes('VANZAI社直契約');

      const introducerInput = window.prompt('紹介者/下請けを入力してください（VANZAI直契約の場合は空欄可）', currentIntroducer || '');
      if (!isVanzaiDirect && (!introducerInput || !String(introducerInput).trim())) {
        event.error = '紹介者/下請けは必須です（経由先がVANZAI以外）。';
        return event;
      }

      return fetchNextWorkerId().then((nextId) => {
        record[FIELDS.group].value = String(groupInput).trim();
        record[FIELDS.introducer].value = String(introducerInput || '').trim();
        record[FIELDS.workerId].value = nextId;
        record[FIELDS.isActive].value = '有効';
        return event;
      });
    }).catch((err) => {
      event.error = `承諾処理に失敗しました: ${err && err.message ? err.message : err}`;
      return event;
    });
  });
})();
