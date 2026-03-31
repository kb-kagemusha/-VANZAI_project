/**
 * A01: 郵便番号から住所自動入力
 * 郵便番号を入力すると、都道府県と市区町村を自動入力
 */
(function() {
  'use strict';

  console.log('[A01 postal] ready');

  var cache = {
    normalized: '',
    result: null,
    ts: 0
  };

  var lastSearch = {
    normalized: '',
    status: '',
    message: ''
  };

  var saveBlock = {
    enabled: false,
    normalized: '',
    message: ''
  };

  var lastDialog = {
    message: '',
    ts: 0
  };

  // 郵便番号検索API（無料）
  var ZIPCODE_API_URL = 'https://zipcloud.ibsnet.co.jp/api/search';

  var lastApplied = {
    normalized: '',
    pref: '',
    city: ''
  };

  function ensureDialogElements() {
    var existing = document.querySelector('[data-kuroko-postal-dialog="1"]');
    if (existing) return existing;

    var overlay = document.createElement('div');
    overlay.setAttribute('data-kuroko-postal-dialog', '1');
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.display = 'none';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';
    overlay.style.background = 'rgba(15, 23, 42, 0.55)';
    overlay.style.zIndex = '9999';

    var card = document.createElement('div');
    card.style.width = 'min(520px, 92vw)';
    card.style.background = '#0f172a';
    card.style.color = '#f8fafc';
    card.style.border = '1px solid #1f2937';
    card.style.borderRadius = '14px';
    card.style.boxShadow = '0 24px 60px rgba(0,0,0,0.45)';
    card.style.padding = '18px 20px 16px';
    card.style.fontFamily = '"Segoe UI", "Meiryo", sans-serif';

    var title = document.createElement('div');
    title.textContent = '郵便番号エラー';
    title.style.fontSize = '16px';
    title.style.fontWeight = '700';
    title.style.marginBottom = '8px';

    var message = document.createElement('div');
    message.setAttribute('data-kuroko-postal-dialog-message', '1');
    message.style.fontSize = '14px';
    message.style.lineHeight = '1.6';

    var actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.justifyContent = 'flex-end';
    actions.style.marginTop = '16px';

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = '閉じる';
    closeBtn.style.background = '#38bdf8';
    closeBtn.style.color = '#0b1220';
    closeBtn.style.border = 'none';
    closeBtn.style.borderRadius = '10px';
    closeBtn.style.padding = '8px 14px';
    closeBtn.style.fontWeight = '700';
    closeBtn.style.cursor = 'pointer';
    closeBtn.addEventListener('click', function() {
      overlay.style.display = 'none';
    });

    actions.appendChild(closeBtn);
    card.appendChild(title);
    card.appendChild(message);
    card.appendChild(actions);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    return overlay;
  }

  function showPostalDialog(message) {
    var overlay = ensureDialogElements();
    if (!overlay) return;
    var msg = overlay.querySelector('[data-kuroko-postal-dialog-message="1"]');
    if (msg) msg.textContent = message || '';
    overlay.style.display = 'flex';
  }

  function showPostalDialogOnce(message) {
    var now = Date.now();
    if (message && lastDialog.message === message && (now - lastDialog.ts) < 1200) return;
    lastDialog.message = message || '';
    lastDialog.ts = now;
    showPostalDialog(message);
  }

  function clearPostalStatus() {
    var overlay = document.querySelector('[data-kuroko-postal-dialog="1"]');
    if (overlay) overlay.style.display = 'none';
  }

  function isNotFoundError(err) {
    return !!(err && (err.code === 'ZIP_NOT_FOUND' || err.code === 'ZIP_INVALID'));
  }

  function updateLastSearch(normalized, status, message) {
    lastSearch.normalized = normalized || '';
    lastSearch.status = status || '';
    lastSearch.message = message || '';
  }

  function markSaveBlocked(normalized, message) {
    saveBlock.enabled = true;
    saveBlock.normalized = normalized || '';
    saveBlock.message = message || '';
  }

  function clearSaveBlocked() {
    saveBlock.enabled = false;
    saveBlock.normalized = '';
    saveBlock.message = '';
  }

  function clearAutoFilledAddressIfStillSame() {
    try {
      var current = kintone.app.record.get();
      if (!current || !current.record) return;
      if (!current.record.address_pref || !current.record.address_city) return;

      var pref = current.record.address_pref.value || '';
      var city = current.record.address_city.value || '';

      // 直近の自動入力結果と同じなら、誤認防止のためクリアする
      if (pref === lastApplied.pref && city === lastApplied.city && (pref || city)) {
        current.record.address_pref.value = '';
        current.record.address_city.value = '';
        kintone.app.record.set({ record: current.record });
      }
    } catch (e) {
      // noop
    }
  }

  /**
   * 郵便番号をフォーマット（ハイフンを除去）
   */
  function normalizeZipcode(zipcode) {
    if (!zipcode) return '';
    return zipcode.replace(/[^\d]/g, '');
  }

  /**
   * 郵便番号から住所を検索
   */
  function searchAddress(zipcode) {
    var normalized = normalizeZipcode(zipcode);
    
    if (normalized.length !== 7) {
      var eLen = new Error('郵便番号は7桁で入力してください');
      eLen.code = 'ZIP_INVALID';
      updateLastSearch(normalized, 'invalid', eLen.message);
      markSaveBlocked(normalized, eLen.message);
      return kintone.Promise.reject(eLen);
    }

    var url = ZIPCODE_API_URL + '?zipcode=' + normalized;
    
    return kintone.proxy(url, 'GET', {}, {})
      .then(function(args) {
        var body = args[0];
        var data = JSON.parse(body);
        
        if (data.status !== 200) {
          var eStatus = new Error(data && data.message ? data.message : '郵便番号が見つかりませんでした');
          eStatus.code = 'ZIP_NOT_FOUND';
          updateLastSearch(normalized, 'not_found', eStatus.message);
          markSaveBlocked(normalized, eStatus.message);
          throw eStatus;
        }
        
        if (!data.results || data.results.length === 0) {
          var eEmpty = new Error('該当する住所が見つかりませんでした');
          eEmpty.code = 'ZIP_NOT_FOUND';
          updateLastSearch(normalized, 'not_found', eEmpty.message);
          markSaveBlocked(normalized, eEmpty.message);
          throw eEmpty;
        }
        
        // 最初の結果を返す
        updateLastSearch(normalized, 'ok', '');
        clearSaveBlocked();
        return data.results[0];
      });
  }

  function dispatchInputEvents(input) {
    try {
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.dispatchEvent(new Event('blur', { bubbles: true }));
    } catch (e) {
      // noop
    }
  }

  function findInputNearLabel(labelText) {
    var nodes = document.querySelectorAll('.control-label-gaia, .field-label-gaia, label, th, span');
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var t = (n.textContent || '').replace(/\s+/g, ' ').trim();
      if (t !== labelText) continue;

      var container = null;
      if (n.closest) {
        container = n.closest('.field-gaia, .row-gaia, tr, .gaia-argoui-field, .recordlist-row, div');
      }
      if (!container) container = n.parentElement;
      if (!container) continue;

      var input = container.querySelector('input, textarea');
      if (!input && container.nextElementSibling) {
        input = container.nextElementSibling.querySelector('input, textarea');
      }
      if (!input && n.parentElement) {
        var p = n.parentElement;
        for (var hop = 0; hop < 6 && p; hop++) {
          input = p.querySelector('input, textarea');
          if (input) break;
          p = p.parentElement;
        }
      }
      if (input) return input;
    }
    return null;
  }

  function applyAddressToCurrentRecord(result) {
    function trySetDom(fieldCode, value) {
      var el = null;
      try {
        el = kintone.app.record.getFieldElement(fieldCode);
      } catch (e) {
        el = null;
      }

      var candidates = [];
      if (el) {
        candidates.push(el);
      }
      // フォールバック: data-field-code
      var q = document.querySelector('[data-field-code="' + fieldCode + '"]');
      if (q) {
        candidates.push(q);
      }

      for (var i = 0; i < candidates.length; i++) {
        var root = candidates[i];
        var input = root.querySelector('input, textarea');
        if (input) {
          input.value = value;
          dispatchInputEvents(input);
          return true;
        }

        // 表示専用の可能性（span/div等）
        var textEl = root.querySelector('.control-value-gaia, .recordlist-cell, span, div');
        if (textEl && textEl.childElementCount === 0) {
          textEl.textContent = value;
          return true;
        }
      }
      return false;
    }

    function trySetDomByLabel(labelText, value) {
      var input = findInputNearLabel(labelText);
      if (!input) return false;
      input.value = value;
      dispatchInputEvents(input);
      return true;
    }

    function doApply(tag) {
      try {
        var current = kintone.app.record.get();
        if (!current || !current.record) {
          console.warn('[A01 postal] apply skipped (no current record):', tag);
          return;
        }

        if (!current.record.address_pref) {
          console.error('[A01 postal] missing field: address_pref');
        }
        if (!current.record.address_city) {
          console.error('[A01 postal] missing field: address_city');
        }

        console.log('[A01 postal] applying:', tag, {
          before_pref: current.record.address_pref ? current.record.address_pref.value : undefined,
          before_city: current.record.address_city ? current.record.address_city.value : undefined
        });

        if (current.record.address_pref) current.record.address_pref.value = result.address1;
        if (current.record.address_city) current.record.address_city.value = result.address2 + result.address3;

        lastApplied.pref = result.address1;
        lastApplied.city = result.address2 + result.address3;

        // UI反映（タイミングによっては直後にKintoneが再描画するので、短い遅延で再適用もする）
        kintone.app.record.set({ record: current.record });

        var after = kintone.app.record.get();
        var domPref = trySetDom('address_pref', result.address1);
        var domCity = trySetDom('address_city', result.address2 + result.address3);

        if (!domPref) domPref = trySetDomByLabel('都道府県', result.address1);
        if (!domCity) domCity = trySetDomByLabel('市区町村', result.address2 + result.address3);

        console.log('[A01 postal] applied:', tag, {
          after_pref: after && after.record && after.record.address_pref ? after.record.address_pref.value : undefined,
          after_city: after && after.record && after.record.address_city ? after.record.address_city.value : undefined,
          dom_pref: domPref,
          dom_city: domCity
        });

        clearPostalStatus();
        clearSaveBlocked();
      } catch (e) {
        console.error('[A01 postal] apply failed:', tag, e);
      }
    }

    // 直後/少し遅延の2回で反映を安定化
    doApply('t0');
    setTimeout(function() { doApply('t120'); }, 120);
  }

  var lastNormalized = '';
  var inFlightToken = null;

  function onPostalCodeChange(event) {
    var zipcode = '';
    if (event && event.changes && event.changes.field && typeof event.changes.field.value === 'string') {
      zipcode = event.changes.field.value;
    } else if (event && event.record && event.record.postal_code) {
      zipcode = event.record.postal_code.value;
    }

    var normalized = normalizeZipcode(zipcode);
    if (normalized.length !== 7) {
      return event;
    }
    if (saveBlock.enabled && saveBlock.normalized === normalized) {
      return event;
    }
    if (normalized === lastNormalized) {
      return event;
    }
    lastNormalized = normalized;

    // 以前の自動入力住所が残っていると誤認するので、必要なら先にクリア
    clearAutoFilledAddressIfStillSame();
    clearPostalStatus();
    if (!(saveBlock.enabled && saveBlock.normalized === normalized)) {
      updateLastSearch(normalized, '', '');
      clearSaveBlocked();
    }

    console.log('[A01 postal] searching:', normalized);
    var token = {};
    inFlightToken = token;

    // changeイベントはThenableをreturnできないので、ここではeventを返しつつ非同期処理
    searchAddress(zipcode)
      .then(function(result) {
        if (inFlightToken !== token) return;
        console.log('[A01 postal] found:', result.address1 + result.address2 + result.address3);

        lastApplied.normalized = normalized;

        cache.normalized = normalized;
        cache.result = result;
        cache.ts = Date.now();

        applyAddressToCurrentRecord(result);
      })
      .catch(function(error) {
        if (inFlightToken !== token) return;
        console.error('[A01 postal] error:', error);

        if (isNotFoundError(error)) {
          var msgNotFound = '入力された郵便番号は存在しません。郵便番号（7桁）を確認してください。';
          markSaveBlocked(normalized, msgNotFound);
          if (!(saveBlock.enabled && saveBlock.normalized === normalized)) {
            showPostalDialogOnce(msgNotFound);
          }
        } else {
          showPostalDialogOnce('住所の取得に失敗しました: ' + (error && error.message ? error.message : 'unknown error'));
        }
      });

    return event;
  }

  function applyToEventRecord(event, result) {
    if (!event || !event.record) return event;
    if (event.record.address_pref) event.record.address_pref.value = result.address1;
    if (event.record.address_city) event.record.address_city.value = result.address2 + result.address3;

    lastApplied.pref = result.address1;
    lastApplied.city = result.address2 + result.address3;
    clearSaveBlocked();
    return event;
  }

  function setPostalErrorOnEvent(event, message) {
    if (!event || !event.record) return event;
    if (event.record.postal_code) {
      event.record.postal_code.error = message;
      event.record.postal_code.value = '';
    }
    if (event.record.address_pref) {
      event.record.address_pref.value = '';
    }
    if (event.record.address_city) {
      event.record.address_city.value = '';
    }
    event.error = message;
    return event;
  }

  function ensureAddressOnSubmit(event) {
    try {
      var zipcode = event && event.record && event.record.postal_code ? event.record.postal_code.value : '';
      var normalized = normalizeZipcode(zipcode);

      // 空欄は許容、入力がある場合は7桁必須
      if (zipcode && normalized.length !== 7) {
        var msgLen = '郵便番号は7桁で入力してください。';
        showPostalDialogOnce(msgLen);
        markSaveBlocked(normalized, msgLen);
        return setPostalErrorOnEvent(event, msgLen);
      }
      if (!normalized) {
        return kintone.Promise.resolve(event);
      }

      // すでに入っているなら何もしない
      var pref = event.record.address_pref ? event.record.address_pref.value : '';
      var city = event.record.address_city ? event.record.address_city.value : '';
      if (pref && city) {
        return kintone.Promise.resolve(event);
      }

      // 直近キャッシュがあればそれを使う
      if (cache.result && cache.normalized === normalized && (Date.now() - cache.ts) < 5 * 60 * 1000) {
        console.log('[A01 postal] submit uses cache:', normalized);
        return kintone.Promise.resolve(applyToEventRecord(event, cache.result));
      }

      // 直近の検索が失敗している場合は保存をブロック
      if (lastSearch.normalized === normalized && (lastSearch.status === 'not_found' || lastSearch.status === 'invalid')) {
        var msgKnown = '存在しない郵便番号です。郵便番号（7桁）を確認してください。';
        showPostalDialogOnce(msgKnown);
        markSaveBlocked(normalized, msgKnown);
        return setPostalErrorOnEvent(event, msgKnown);
      }

      console.log('[A01 postal] submit fetch:', normalized);
      return searchAddress(zipcode)
        .then(function(result) {
          cache.normalized = normalized;
          cache.result = result;
          cache.ts = Date.now();
          return applyToEventRecord(event, result);
        })
        .catch(function(error) {
          console.error('[A01 postal] submit error:', error);

          var msgErr = isNotFoundError(error)
            ? '存在しない郵便番号です。郵便番号（7桁）を確認してください。'
            : ('郵便番号から住所取得に失敗しました: ' + (error && error.message ? error.message : 'unknown error'));

          showPostalDialogOnce(msgErr);
          markSaveBlocked(normalized, msgErr);
          return setPostalErrorOnEvent(event, msgErr);
        });
    } catch (e) {
      console.error('[A01 postal] submit exception:', e);
      event.error = '住所自動入力で例外が発生しました。';
      return kintone.Promise.resolve(event);
    }
  }

  function bindPostalInputAutoFill() {
    var bound = false;
    var attempts = 0;
    var last = '';

    function bind() {
      if (bound) return;
      attempts += 1;
      var input = findInputNearLabel('郵便番号');
      if (!input) {
        if (attempts === 1) console.warn('[A01 postal] waiting postal input by label');
        if (attempts < 60) setTimeout(bind, 200);
        if (attempts === 60) console.error('[A01 postal] bind failed: postal input not found by label');
        return;
      }
      if (input.dataset && input.dataset.kurokoPostalInputBound === '1') {
        bound = true;
        return;
      }
      if (input.dataset) input.dataset.kurokoPostalInputBound = '1';

      var timer = null;
      var handler = function() {
        if (timer) clearTimeout(timer);
        timer = setTimeout(function() {
          var zipcode = input.value;
          var normalized = normalizeZipcode(zipcode);
          if (normalized.length !== 7 || normalized === last) return;
          last = normalized;

          clearAutoFilledAddressIfStillSame();
          clearPostalStatus();
          updateLastSearch(normalized, '', '');
          clearSaveBlocked();

          console.log('[A01 postal] input trigger searching:', normalized);
          searchAddress(zipcode)
            .then(function(result) {
              console.log('[A01 postal] input found:', result.address1 + result.address2 + result.address3);
              cache.normalized = normalized;
              cache.result = result;
              cache.ts = Date.now();
              lastApplied.normalized = normalized;
              applyAddressToCurrentRecord(result);
            })
            .catch(function(error) {
              console.error('[A01 postal] input error:', error);
              if (isNotFoundError(error)) {
                var msgInput = '入力された郵便番号は存在しません。郵便番号（7桁）を確認してください。';
                markSaveBlocked(normalized, msgInput);
                showPostalDialogOnce(msgInput);
              } else {
                showPostalDialogOnce('住所の取得に失敗しました: ' + (error && error.message ? error.message : 'unknown error'));
              }
            });
        }, 400);
      };

      input.addEventListener('input', handler);
      input.addEventListener('change', handler);
      input.addEventListener('blur', handler);
      console.log('[A01 postal] bound postal input events (by label)');
      bound = true;
    }

    bind();
  }

  kintone.events.on([
    'app.record.create.change.postal_code',
    'app.record.edit.change.postal_code',
    'app.record.index.edit.change.postal_code'
  ], onPostalCodeChange);

  // 保存時に住所が空なら必ず補完してから送信
  kintone.events.on([
    'app.record.create.submit',
    'app.record.edit.submit',
    'app.record.index.edit.submit'
  ], ensureAddressOnSubmit);

  kintone.events.on([
    'app.record.create.submit.validate',
    'app.record.edit.submit.validate'
  ], function(event) {
    var zipcode = event && event.record && event.record.postal_code ? event.record.postal_code.value : '';
    var normalized = normalizeZipcode(zipcode);
    if (!zipcode) return event;

    if (normalized.length !== 7) {
      var msgLen = '郵便番号は7桁で入力してください。';
      showPostalDialogOnce(msgLen);
      markSaveBlocked(normalized, msgLen);
      return setPostalErrorOnEvent(event, msgLen);
    }

    if (saveBlock.enabled && saveBlock.normalized === normalized) {
      var msgBlock = saveBlock.message || '存在しない郵便番号です。郵便番号（7桁）を確認してください。';
      showPostalDialogOnce(msgBlock);
      return setPostalErrorOnEvent(event, msgBlock);
    }
    return event;
  });

  kintone.events.on([
    'app.record.create.show',
    'app.record.edit.show',
    'app.record.index.edit.show'
  ], function(event) {
    bindPostalInputAutoFill();
    return event;
  });

})();
