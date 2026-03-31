(() => {
  'use strict';

  const MASTER_APP_ID = 164;
  const LABELS = {
    major: '大カテゴリ',
    middle: '中カテゴリ',
    minor: '小カテゴリ'
  };

  const state = {
    fieldCodes: null,
    options: null
  };

  const normalizeLabel = (value) => (value || '').replace(/\s+/g, '');
  const normalizeCategoryKey = (value) => String(value || '').trim().replace(/[：:]/g, '');
  const normalizeMiddleOrderKey = (value) => String(value || '').trim().replace(/[\s：:]/g, '');
  const extract巡回Price = (value) => {
    const match = normalizeMiddleOrderKey(value).match(/店巡回(\d+)円/);
    return match ? Number(match[1]) : null;
  };
  const sortMiddle = (items) => Array.from(new Set(items.filter(Boolean))).sort((a, b) => {
    const aPrice = extract巡回Price(a);
    const bPrice = extract巡回Price(b);
    if (aPrice !== null && bPrice !== null) {
      return bPrice - aPrice;
    }
    return a.localeCompare(b, 'ja');
  });

  const fetchFormFields = async (appId) => {
    const params = { app: appId };
    const response = await kintone.api(kintone.api.url('/k/v1/app/form/fields.json', true), 'GET', params);
    return response.properties || {};
  };

  const resolveFieldCodes = async () => {
    if (state.fieldCodes) {
      return state.fieldCodes;
    }
    const properties = await fetchFormFields(kintone.app.getId());
    const labelToCode = {};
    Object.keys(properties).forEach((code) => {
      const label = properties[code].label || '';
      labelToCode[normalizeLabel(label)] = code;
    });

    const fieldCodes = {
      major: labelToCode[normalizeLabel(LABELS.major)],
      middle: labelToCode[normalizeLabel(LABELS.middle)],
      minor: labelToCode[normalizeLabel(LABELS.minor)]
    };

    state.fieldCodes = fieldCodes;
    return fieldCodes;
  };

  const fetchCategoryRecords = async () => {
    const params = {
      app: MASTER_APP_ID,
      fields: ['name', 'category_level', 'parent_major', 'parent_middle'],
      query: 'order by name asc'
    };
    const response = await kintone.api(kintone.api.url('/k/v1/records.json', true), 'GET', params);
    return response.records || [];
  };

  const buildCategoryOptions = async () => {
    if (state.options) {
      return state.options;
    }

    const records = await fetchCategoryRecords();
    const majors = [];
    const middleMap = {};
    const minorMap = {};

    const normalizeValue = (value) => String(value || '').trim();

    records.forEach((record) => {
      const level = normalizeValue(record.category_level?.value || '');
      const name = normalizeValue(record.name?.value || '');
      const parentMajorRaw = normalizeValue(record.parent_major?.value || '');
      const parentMiddle = normalizeValue(record.parent_middle?.value || '');

      if (!name) {
        return;
      }

      if (level === 'major') {
        majors.push(name);
      } else if (level === 'middle') {
        parentMajorRaw.split('|').map((value) => normalizeValue(value)).filter(Boolean).forEach((parentMajor) => {
          if (!middleMap[parentMajor]) {
            middleMap[parentMajor] = [];
          }
          middleMap[parentMajor].push(name);
        });
      } else if (level === 'minor') {
        const parentKey = normalizeCategoryKey(parentMiddle);
        if (!minorMap[parentKey]) {
          minorMap[parentKey] = [];
        }
        minorMap[parentKey].push(name);
      }
    });

    const sortUnique = (items) => Array.from(new Set(items.filter(Boolean)))
      .sort((a, b) => a.localeCompare(b, 'ja'));
    const options = {
      majors: sortUnique(majors),
      middleMap: {},
      middleAll: sortMiddle(records.filter((record) => normalizeValue(record.category_level?.value || '') === 'middle')
        .map((record) => normalizeValue(record.name?.value || ''))),
      minorMap: {}
    };

    Object.keys(middleMap).forEach((key) => {
      options.middleMap[key] = sortMiddle(middleMap[key]);
    });

    Object.keys(minorMap).forEach((key) => {
      options.minorMap[key] = sortUnique(minorMap[key]);
    });

    state.options = options;
    return options;
  };

  const setSelectOptions = (selectEl, options, placeholder) => {
    if (!selectEl) {
      return;
    }
    selectEl.innerHTML = '';
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = placeholder;
    selectEl.appendChild(defaultOption);

    options.forEach((option) => {
      const opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option;
      selectEl.appendChild(opt);
    });
  };

  const getSelectElement = (fieldCode) => {
    if (!fieldCode) {
      return null;
    }
    const element = kintone.app.record.getFieldElement(fieldCode);
    if (!element) {
      return null;
    }
    return element.querySelector('select');
  };

  const applyInitialValues = (record, selects) => {
    if (record && selects.major && record[selects.major.code]) {
      selects.major.select.value = record[selects.major.code].value || '';
    }
    if (record && selects.middle && record[selects.middle.code]) {
      selects.middle.select.value = record[selects.middle.code].value || '';
    }
    if (record && selects.minor && record[selects.minor.code]) {
      selects.minor.select.value = record[selects.minor.code].value || '';
    }
  };

  const initCascade = async (event) => {
    const fieldCodes = await resolveFieldCodes();
    const options = await buildCategoryOptions();

    if (!fieldCodes.major || !fieldCodes.middle || !fieldCodes.minor) {
      console.warn('カテゴリフィールドのコードを取得できませんでした。');
      return event;
    }

    const majorSelect = getSelectElement(fieldCodes.major);
    const middleSelect = getSelectElement(fieldCodes.middle);
    const minorSelect = getSelectElement(fieldCodes.minor);

    if (!majorSelect || !middleSelect || !minorSelect) {
      console.warn('カテゴリフィールドのselect要素が取得できませんでした。');
      return event;
    }

    setSelectOptions(majorSelect, options.majors, '選択してください');
    setSelectOptions(middleSelect, [], '大カテゴリを選択');
    setSelectOptions(minorSelect, [], '中カテゴリを選択');

    applyInitialValues(event.record, {
      major: { code: fieldCodes.major, select: majorSelect },
      middle: { code: fieldCodes.middle, select: middleSelect },
      minor: { code: fieldCodes.minor, select: minorSelect }
    });

    const updateMiddle = () => {
      const majorValue = majorSelect.value;
      let middleOptions = options.middleMap[majorValue] || [];
      if (middleOptions.length === 0) {
        middleOptions = options.middleAll || [];
      }
      setSelectOptions(middleSelect, middleOptions, '中カテゴリを選択');
      setSelectOptions(minorSelect, [], '中カテゴリを選択');
    };

    const updateMinor = () => {
      const middleValue = middleSelect.value;
      const middleKey = normalizeCategoryKey(middleValue);
      const minorOptions = options.minorMap[middleKey] || [];
      setSelectOptions(minorSelect, minorOptions, '小カテゴリを選択');
    };

    majorSelect.addEventListener('change', updateMiddle);
    middleSelect.addEventListener('change', updateMinor);

    if (majorSelect.value) {
      updateMiddle();
      if (middleSelect.value) {
        updateMinor();
      }
    }

    return event;
  };

  kintone.events.on(['app.record.create.show', 'app.record.edit.show'], initCascade);
})();
