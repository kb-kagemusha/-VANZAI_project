(function () {
  'use strict';

  // カテゴリマスタデータキャッシュ（App164から読み込む）
  let CATEGORY_DATA = null;
  let CATEGORY_OPTIONS = null;
  let CATEGORY_RULES = null;
  const FRONT_DASHBOARD_BUILD_MARKER = 'FD-2026-02-18-WORKER-ULID-MAP-03';

  // SQLite workers テーブル由来の ULID→氏名 静的マップ（kintone DROP_DOWN keyに氏名が入れられないため埋め込み）
  // 新規稼働者追加時は scripts/_gen_worker_map.py を実行してこのマップを更新すること
  const WORKER_ULID_MAP = {
    "01KFZS7DRB0X156CWR0G1JPBVR": "山田太郎",
    "01KFZS7DRB0X156CWR0G1JPBVS": "佐藤花子",
    "01KFZS7DRB0X156CWR0G1JPBVT": "鈴木次郎",
    "01KG1DJP5237AG0MQJ4FTV5Y97": "Aki Tanaka",
    "01KG1DJP53K8FP1DSARAZZFHP3": "Hiro Sato",
    "01KG1DJP546ACB82PHXK9Q0FV5": "Mina Suzuki",
    "01KG1DJP55CGBWSP6FVC4ANJZW": "Ken Yamamoto",
    "01KG1DJP56DQHP704R8BSMAXAZ": "Yui Kobayashi",
    "01KG1DJP57023DAP3YAX06BEET": "Sora Ito",
    "01KG1DJP57023DAP3YAX06BEEV": "Rina Nakamura",
    "01KG1DJP587N078ZT29GY43RXQ": "Daichi Watanabe",
    "01KG1DJP59TE6507SDQ8G9TJ3E": "Nao Kato",
    "01KG1DJP59TE6507SDQ8G9TJ3F": "Koki Fujita",
  };

  const GUEST_SPACE_ID = 3;

  const CONFIG = {
    apps: {
      suppliers: 311,
      sites: 166,
      workers: 165,
      clients: 167,
      projects: 160,
      project_assignments: 307,
      project_types: 164,
      actuals: 168,
      assignments: 158,
      incentives: 150,
      expenses: 151,
      invoices: 171,
      payouts: 173,
      staff_managers: 309,
      vanzai_staff: 313
    },
    invoicePdf: {
      uploadTarget: 'kintone',
      externalUploadUrl: '',
      externalOpenUrlTemplate: ''
    },
    payoutPdf: {
      uploadTarget: 'kintone',
      externalUploadUrl: '',
      externalOpenUrlTemplate: ''
    },
    suppliers: {
      resolveByLabel: true,
      fields: {
        corporate_worker_id: { label: '稼働者法人ID', required: true },
        partner_category: { label: '区分', type: 'select', options: ['', '紹介者', '下請け'] },
        partner_entity: { label: '法人or個人', type: 'select', options: ['', '法人', '個人', '企業'] },
        company_name: { label: '会社名' },
        company_name_furigana: { label: '会社名（フリガナ）' },
        representative_name: { label: '代表者名（フルネーム漢字）' },
        representative_name_furigana: { label: '代表者名（フリガナ）' },
        phone: { label: '電話番号' },
        email: { label: 'メールアドレス' },
        zipcode: { label: '郵便番号' },
        pref: { label: '都道府県' },
        city_etc: { label: '市区町村以下' },
        name_of_building: { label: '建物名・部屋番号' },
        bank_name: { label: '振込口座(銀行名)' },
        bank_branch: { label: '振込口座(支店名)' },
        bank_branch_number: { label: '振込口座(支店番号)' },
        bank_account_type: { label: '振込口座(口座種別)' },
        bank_account_number: { label: '振込口座(口座番号7桁)' },
        bank_account_holder_kana: { label: '振込口座(カタカナ)' },
        invoice_registration_status: { label: '適格請求書発行事業者の登録番号_取得有無' },
        invoice_registration_number: { label: '適格請求書発行事業者の登録番号 （T+13桁の番号を記入してください）' },
        address_line1: { label: '住所 (郵便番号･建物名･部屋番号を除く)' },
        address_line2: { label: '住所(建物名･部屋番号のみ)' },
        is_active: { label: '有効・無効', type: 'select', options: ['有効', '無効'], defaultValue: '無効' },
        memos: { label: '備考', type: 'textarea' }
      },
      autoId: { field: 'corporate_worker_id', prefix: 'CPR', width: 4 }
    },
    sites: {
      fields: {
        site_id: { label: '現場ID', required: true },
        category_major: { label: '大カテゴリ', type: 'select', options: [''] },
        category_middle: { label: '中カテゴリ', type: 'select', options: [''] },
        category_minor: { label: '小カテゴリ', type: 'select', options: [''] },
        name: { label: '現場名', required: true },
        address: { label: '現場住所' },
        notes: { label: '備考', type: 'textarea' }
      },
      autoId: { field: 'site_id', prefix: 'SIT', width: 3 }
    },
    workers: {
      resolveByLabel: true,
      fields: {
        worker_id: { label: '稼働者ID', required: true },
        last_name: { label: '氏名(姓)', required: true },
        first_name: { label: '氏名(名)', required: true },
        lastname_furigana: { label: '姓(フリガナ)' },
        firstname_furigana: { label: '名(フリガナ)' },
        via_destination: { label: '経由先', type: 'select', options: ['下請け', '紹介', 'VANZAI直接'] },
        introducer_supplier: { label: '紹介者/下請け' },
        sex: { label: '性別', type: 'select', options: ['男性', '女性'] },
        bussiness_name: { label: '個人事業主屋号' },
        zipcode: { label: '郵便番号' },
        pref: { label: '都道府県' },
        city_etc: { label: '市区町村以下' },
        name_of_building: { label: '建物名･部屋番号' },
        email: { label: 'メールアドレス' },
        phone: { label: '携帯電話番号' },
        emergency_contact_name: { label: '緊急連絡先氏名(カナ)' },
        emergency_contact_phone: { label: '緊急連絡先' },
        bank_name: { label: '振込口座(銀行名)' },
        bank_branch: { label: '振込口座(支店名)' },
        bank_branch_number: { label: '振込口座(支店番号)' },
        bank_account_type: { label: '振込口座(口座種別)' },
        bank_account_number: { label: '振込口座(口座番号7桁)' },
        bank_account_holder: { label: '振込口座(名義)' },
        id_document: { label: '身分証提出' },
        invoice_registration_status: { label: '適格請求書発行事業者の登録番号_取得有無' },
        invoice_registration_number: { label: '適格請求書発行事業者の登録番号 （T+13桁の番号を記入してください）' },
        address_line1: { label: '住所 (郵便番号･建物名･部屋番号を除く)' },
        address_line2: { label: '住所(建物名･部屋番号のみ)' },
        is_active: { label: '有効・無効', type: 'select', options: ['有効', '無効'], defaultValue: '無効' },
        memos: { label: '備考', type: 'textarea' }
      },
      autoId: { field: 'worker_id', prefix: 'WRK', width: 4 }
    },
    staff_managers: {
      fields: {
        staff_id: { label: 'ID', required: true },
        client_company: { label: 'クライアント企業', required: true },
        name: { label: '職員名', required: true },
        phone: { label: '電話番号' },
        email: { label: 'メールアドレス' },
        notes: { label: '備考', type: 'textarea' }
      },
      resolveByLabelFlexible: true,
      autoId: { field: 'staff_id', prefix: 'STM', width: 3 }
    },
    vanzai_staff: {
      fields: {
        id: { label: 'ID', required: true },
        name: { label: '職員名' },
        role: { label: '役職', type: 'select' },
        phone: { label: '電話番号' },
        mail: { label: 'メールアドレス' },
        memo: { label: '備考', type: 'textarea' }
      },
      resolveByLabelFlexible: true,
      autoId: { field: 'id', prefix: 'VZ', width: 4 }
    },
    clients: {
      fields: {
        client_id: { label: 'クライアントID', required: true },
        name: { label: 'クライアント名', required: true },
        code: { label: 'コード' },
        address: { label: '住所', type: 'textarea' },
        billing_email: { label: '請求先メール' },
        notes: { label: '備考', type: 'textarea' }
      },
      autoId: { field: 'client_id', prefix: 'CLI', width: 3 }
    },
    projects: {
      fields: {
        project_id: { label: '案件ID', required: true },
        name: { label: '案件名（自動）', required: true },
        project_category_major: {
          label: '大カテゴリ',
          type: 'select',
          required: true
        },
        project_category_middle: {
          label: '中カテゴリ',
          type: 'select'
        },
        project_category_minor: {
          label: '小カテゴリ',
          type: 'select'
        },
        request_project_type: { label: '案件種別', type: 'select', required: true },
        request_date: { label: '日時（開始）', type: 'date', required: true },
        request_end_date: { label: '日時（終了）', type: 'date' },
        request_weekday: { label: '曜日（自動）', hidden: true },
        request_facility: { label: '施設名', required: true },
        request_event_name: { label: 'イベント名' },
        request_address: { label: '住所', type: 'textarea' },
        request_content: { label: '内容', type: 'textarea' },
        director_count: { label: '必要人員', type: 'number', layout: 'half' },
        staff_count: { label: 'スタッフ人数', type: 'number', layout: 'half' },
        meeting_time: { label: '集合時間', type: 'time', layout: 'half' },
        work_start_time: { label: '開始時刻', type: 'time', layout: 'half' },
        work_end_time: { label: '終了時刻', type: 'time', layout: 'half' },
        work_hours: { label: '稼働時間(時間)（自動）', type: 'number', hidden: true },
        dismissal_time: { label: '解散時間', type: 'time', layout: 'half' },
        director_unit_price: { label: '報酬_ディレクター(円/日/人)', type: 'number', layout: 'half' },
        staff_unit_price: { label: '報酬_スタッフ(円/日/人)', type: 'number', layout: 'half' },
        notes: { label: '備考', type: 'textarea' }
      },
      autoId: { field: 'project_id', prefix: 'PRJ', width: 3 }
    },
    project_assignments: {
      resolveByLabel: true,
      fields: {
        assignment_id: { label: 'ID', required: true },
        company_name: { label: 'クライアント名', type: 'select', required: true, options: [''] },
        owner_name: { label: 'クライアント責任者', type: 'select', layout: 'half', options: [''] },
        main_staff: { label: 'クライアント担当者', type: 'select', layout: 'half', options: [''] },
        category_major: { label: '大カテゴリ', type: 'select', required: true },
        category_middle: { label: '中カテゴリ', type: 'select', required: true },
        category_minor: { label: '小カテゴリ', type: 'select', required: true },
        sales_flag: { label: '販売', type: 'select', options: ['あり', 'なし'], required: true, defaultValue: 'なし' },
        assignment_title: { label: '案件タイトル', hidden: true },
        facility_name: { label: '施設名' },
        event_name: { label: 'イベント名' },
        address: { label: '住所' },
        start_date: { label: '開始期間', type: 'date', required: true, layout: 'half' },
        end_date: { label: '終了期間', type: 'date', layout: 'half' },
        playing_manager: { label: 'プレイングマネージャー' },
        director: { label: 'ディレクター' },
        assistant_director: { label: 'アシスタントディレクター' },
        field_staff: { label: 'スタッフ' },
        billing_rate_monthly: { label: '必要人数', type: 'number', layout: 'third' },
        headcount_director: { label: 'ディレクター', type: 'number', layout: 'third' },
        headcount_staff: { label: 'スタッフ', type: 'number', layout: 'third' },
        gathering_time: { label: '集合時間', type: 'time', layout: 'half' },
        start_time: { label: '開始時間', type: 'time', layout: 'half' },
        end_time: { label: '終了時間', type: 'time', layout: 'half' },
        dismissal_time: { label: '解散時間', type: 'time', layout: 'half' },
        working_hours: { label: '1日稼働時間(h)', type: 'number', layout: 'half' },
        billing_rate_daily: { label: 'ベース報酬', type: 'number', layout: 'half' },
        detail_url: { label: '詳細リンク' },
        sales_rule: { label: '内容', type: 'textarea' },
        base_reward_director: { label: 'ベース報酬:ディレクター', type: 'number', hidden: true },
        base_reward_assistant_director: { label: 'ベース報酬:アシスタントディレクター', type: 'number', hidden: true },
        base_reward_staff: { label: 'ベース報酬:スタッフ', type: 'number', hidden: true },
        billing_rate_incentive: {
          label: 'インセンティブ',
          type: 'select',
          options: ['', '1件毎/+¥〇〇円', '¥1,000～¥6,000'],
          hidden: true
        },
        notes: { label: '備考', type: 'textarea' }
      },
      fieldCodes: {
        assignment_id: 'assignment_id',
        category_major: 'category_major',
        category_middle: 'category_middle',
        category_minor: 'category_minor',
        assignment_title: 'assignment_title',
        facility_name: 'facility_name',
        event_name: 'event_name',
        start_date: 'start_date',
        end_date: 'end_date',
        address: 'address',
        company_name: 'company_name',
        owner_name: 'owner_name',
        main_staff: 'main_staff',
        gathering_time: 'gathering_time',
        start_time: 'start_time',
        end_time: 'end_time',
        dismissal_time: 'dismissal_time',
        working_hours: 'work_hours',
        detail_url: 'detail_url',
        sales_rule: 'sales_rule',
        billing_rate_monthly: 'headcount_required',
        billing_rate_daily: 'base_reward',
        billing_rate_incentive: 'incentive',
        notes: 'notes',
        headcount_director: 'headcount_director',
        headcount_staff: 'headcount_staff',
        base_reward_director: 'base_reward_director',
        base_reward_staff: 'base_reward_staff',
        base_reward_assistant_director: 'base_reward_assistant_director'
      },
      staffingFieldCodes: {
        company_name: 'company_name',
        owner_name: 'owner_name',
        main_staff: 'main_staff',
        playing_manager: 'playing_manager',
        director: 'director',
        assistant_director: 'assistant_director',
        field_staff: 'field_staff',
        headcount_required: 'headcount_required',
        headcount_director: 'headcount_director',
        headcount_staff: 'headcount_staff',
        incentive: 'incentive'
      },
      autoId: { field: 'assignment_id', prefix: 'drv', width: 3, includeYear: true }
    },
    actuals: {
      fields: {
        assignment_id: { label: '案件ID', type: 'select', required: true, options: [''] },
        worker_id: { label: '稼働者ID', type: 'select', required: true, options: [''] },
        worked_start_time: { label: '出勤時間', type: 'time', required: true, layout: 'half' },
        worked_end_time: { label: '退勤時間', type: 'time', required: true, layout: 'half' },
        sales_count: { label: '販売数（販売ありのみ）', type: 'number', hidden: true },
        memo: { label: '備考', type: 'textarea' }
      }
    },
    invoices: {
      fields: {
        invoice_id: { label: '請求書ID', required: true },
        client_id: { label: 'クライアントID', required: true },
        issue_date: { label: '発行日', type: 'date' },
        total_amount: { label: '請求合計', type: 'number' },
        notes: { label: '備考', type: 'textarea' }
      }
    }
  };

  function ensureStyle() {
    if (document.getElementById('vanzai-front-style')) {
      return;
    }
    const style = document.createElement('style');
    style.id = 'vanzai-front-style';
    style.textContent = `
      .vanzai-front-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
      }
      .vanzai-front-row-title {
        display: inline-block;
        font-size: 12px;
        font-weight: 700;
        color: #111827;
        background: transparent;
        border: none;
        margin-right: 8px;
        margin-bottom: 0;
        white-space: nowrap;
      }
      .vanzai-front-version-badge {
        position: fixed;
        right: 10px;
        bottom: 8px;
        z-index: 9999;
        padding: 2px 6px;
        border-radius: 9999px;
        background: rgba(15, 23, 42, 0.72);
        color: #e5e7eb;
        font-size: 10px;
        letter-spacing: 0.02em;
        pointer-events: none;
        user-select: none;
      }
      .vanzai-front-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 9px 18px;
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        color: #fff;
        font-weight: 600;
        font-size: 14px;
        box-shadow: 0 6px 12px rgba(29, 78, 216, 0.25);
        cursor: pointer;
        transition: transform 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
      }
      .vanzai-front-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 14px rgba(29, 78, 216, 0.3);
      }
      .vanzai-front-btn.secondary {
        background: linear-gradient(135deg, #14b8a6, #0f766e);
        box-shadow: 0 6px 12px rgba(15, 118, 110, 0.25);
      }
      .vanzai-front-btn.tertiary {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        box-shadow: 0 6px 12px rgba(217, 119, 6, 0.25);
      }
      .vanzai-front-btn.quaternary {
        background: linear-gradient(135deg, #8b5cf6, #6d28d9);
        box-shadow: 0 6px 12px rgba(109, 40, 217, 0.25);
      }
      .vanzai-front-btn.mini {
        padding: 8px 14px;
        font-size: 13px;
      }
      .vanzai-front-client-group {
        position: relative;
        display: inline-flex;
        min-width: 180px;
      }
      .vanzai-front-client-slide {
        position: absolute;
        top: calc(100% + 6px);
        left: 0;
        z-index: 20;
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 6px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.98);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.2);
        overflow: hidden;
        max-height: 0;
        opacity: 0;
        transform: translateY(-4px);
        transition: max-height 0.22s ease, opacity 0.18s ease, transform 0.18s ease;
        pointer-events: none;
      }
      .vanzai-front-client-slide.open {
        max-height: 140px;
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
      }
      .vanzai-form-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        align-content: flex-start;
      }
      .vanzai-form-row {
        flex: 1 1 100%;
        min-width: 0;
      }
      .vanzai-form-row.half {
        flex: 1 1 calc(50% - 12px);
      }
      .vanzai-form-row.third {
        flex: 1 1 calc(33.333% - 12px);
      }
      .vanzai-form-row.hidden {
        display: none;
      }
      .vanzai-detail-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 14px;
        color: #0f172a;
        font-size: 13px;
        line-height: 1.6;
      }
      .vanzai-detail-title {
        font-weight: 700;
        margin-bottom: 8px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #64748b;
      }
      .vanzai-detail-list {
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .vanzai-detail-item {
        display: flex;
        gap: 8px;
        padding: 4px 0;
        border-bottom: 1px dashed #e2e8f0;
      }
      .vanzai-detail-item:last-child {
        border-bottom: none;
      }
      .vanzai-detail-key {
        min-width: 90px;
        font-weight: 600;
        color: #475569;
      }
      .vanzai-detail-value {
        color: #0f172a;
        flex: 1;
        word-break: break-word;
      }
    `;
    document.head.appendChild(style);
  }

  function createButton(label, onClick, variant) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = label;
    btn.className = `vanzai-front-btn ${variant || ''}`.trim();
    btn.style.marginRight = '8px';
    btn.addEventListener('click', onClick);
    return btn;
  }

  function openApp(appId) {
    const basePath = GUEST_SPACE_ID ? `/k/guest/${GUEST_SPACE_ID}/` : '/k/';
    location.href = `${basePath}${appId}/`;
  }

  function openAppCreate(appId) {
    const basePath = GUEST_SPACE_ID ? `/k/guest/${GUEST_SPACE_ID}/` : '/k/';
    location.href = `${basePath}${appId}/edit`;
  }

  function openAppWithQuery(appId, query) {
    const basePath = GUEST_SPACE_ID ? `/k/guest/${GUEST_SPACE_ID}/` : '/k/';
    const queryString = query ? `?query=${encodeURIComponent(query)}` : '';
    location.href = `${basePath}${appId}/${queryString}`;
  }

  function openAppRecord(appId, recordId) {
    const basePath = GUEST_SPACE_ID ? `/k/guest/${GUEST_SPACE_ID}/` : '/k/';
    location.href = `${basePath}${appId}/show#record=${encodeURIComponent(String(recordId || ''))}`;
  }

  function createRow(title) {
    const row = document.createElement('div');
    row.className = 'vanzai-front-row';
    if (title) {
      const label = document.createElement('span');
      label.className = 'vanzai-front-row-title';
      label.textContent = title;
      row.appendChild(label);
    }
    return row;
  }

  function buildModal(title, fields, onSubmit) {
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.bottom = '0';
    overlay.style.background = 'rgba(0,0,0,0.4)';
    overlay.style.zIndex = '10000';

    const modal = document.createElement('div');
    modal.style.width = '720px';
    modal.style.maxWidth = 'calc(100vw - 160px)';
    modal.style.margin = '6vh auto';
    modal.style.background = 'linear-gradient(to bottom, #ffffff, #f8fafc)';
    modal.style.borderRadius = '16px';
    modal.style.padding = '24px 28px';
    modal.style.boxShadow = '0 20px 60px rgba(0,0,0,0.3), 0 0 1px rgba(0,0,0,0.1)';
    modal.style.height = '90vh';
    modal.style.maxHeight = '90vh';
    modal.style.display = 'flex';
    modal.style.flexDirection = 'column';
    modal.style.overflow = 'hidden';
    modal.style.border = '1px solid #e2e8f0';
    modal.style.boxSizing = 'border-box';

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';
    header.style.paddingBottom = '14px';
    header.style.borderBottom = '2px solid #e2e8f0';
    const h = document.createElement('h3');
    h.textContent = title;
    h.style.margin = '0';
    h.style.fontSize = '20px';
    h.style.fontWeight = '700';
    h.style.background = 'linear-gradient(135deg, #3b82f6, #8b5cf6)';
    h.style.webkitBackgroundClip = 'text';
    h.style.webkitTextFillColor = 'transparent';
    h.style.backgroundClip = 'text';
    const close = document.createElement('button');
    close.textContent = '×';
    close.style.border = 'none';
    close.style.background = 'transparent';
    close.style.fontSize = '22px';
    close.style.color = '#6b7280';
    close.style.cursor = 'pointer';
    close.addEventListener('click', () => {
      document.body.style.overflow = '';
      document.body.removeChild(overlay);
    });
    header.appendChild(h);
    header.appendChild(close);

    const form = document.createElement('div');
    form.style.marginTop = '12px';
    form.style.flex = '1 1 auto';
    form.style.overflowY = 'auto';
    form.style.overflowX = 'hidden';
    form.className = 'vanzai-form-grid';
    form.style.paddingRight = '4px';

    const inputs = {};
    Object.keys(fields).forEach((code) => {
      const meta = fields[code];
      const row = document.createElement('div');
      row.className = 'vanzai-form-row';
      if (meta.layout === 'half') {
        row.classList.add('half');
      }
      if (meta.layout === 'third') {
        row.classList.add('third');
      }
      if (meta.hidden) {
        row.classList.add('hidden');
      }
      row.dataset.fieldCode = code;

      const label = document.createElement('label');
      label.textContent = meta.label + (meta.required ? ' *' : '');
      label.style.display = 'block';
      label.style.fontSize = '12px';
      label.style.marginBottom = '6px';
      label.style.color = '#374151';

      let input;
      if (meta.type === 'display') {
        input = document.createElement('div');
        input.className = 'vanzai-detail-card';
        input.innerHTML = '<div class="vanzai-detail-title">DETAILS</div><ul class="vanzai-detail-list"></ul>';
      } else if (meta.type === 'textarea') {
        input = document.createElement('textarea');
        input.rows = 3;
      } else if (meta.type === 'select') {
        input = document.createElement('select');
        (meta.options || []).forEach((opt) => {
          const option = document.createElement('option');
          option.value = opt;
          option.textContent = opt;
          input.appendChild(option);
        });
      } else {
        input = document.createElement('input');
        if (meta.type === 'number') {
          input.type = 'number';
        } else if (meta.type === 'date') {
          input.type = 'date';
        } else if (meta.type === 'time') {
          input.type = 'time';
          input.step = '1800';
        } else {
          input.type = 'text';
        }
      }

      if (meta.defaultValue) {
        input.value = meta.defaultValue;
      }

      if (meta.type !== 'display') {
        input.style.width = '100%';
      }
      input.style.padding = '10px 12px';
      input.style.border = '2px solid #e5e7eb';
      input.style.borderRadius = '8px';
      input.style.background = 'white';
      input.style.boxSizing = 'border-box';
      input.style.fontSize = '14px';
      input.style.transition = 'all 0.2s';
      if (meta.type === 'time' || meta.type === 'date') {
        input.style.paddingRight = '32px';
      }
      
      if (meta.type !== 'display') {
        input.addEventListener('focus', () => {
          input.style.borderColor = '#3b82f6';
          input.style.outline = 'none';
          input.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)';
        });
        input.addEventListener('blur', () => {
          input.style.borderColor = '#e5e7eb';
          input.style.boxShadow = 'none';
        });
      }
      
      input.dataset.code = code;

      inputs[code] = input;
      row.appendChild(label);
      row.appendChild(input);
      form.appendChild(row);
    });

    const footer = document.createElement('div');
    footer.style.display = 'flex';
    footer.style.justifyContent = 'flex-end';
    footer.style.flexWrap = 'wrap';
    footer.style.rowGap = '8px';
    footer.style.gap = '12px';
    footer.style.marginTop = '12px';
    footer.style.paddingTop = '12px';
    footer.style.borderTop = '1px solid #e5e7eb';
    footer.style.background = '#f8fafc';
    footer.style.width = '100%';
    footer.style.boxSizing = 'border-box';

    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.textContent = 'キャンセル';
    cancel.className = 'kintoneplugin-button-normal';
    cancel.style.cssText += ';padding:10px 20px;border-radius:8px;font-weight:600;border:2px solid #e5e7eb;background:white;color:#6b7280;cursor:pointer;transition:all 0.2s;';
    cancel.addEventListener('click', () => {
      document.body.style.overflow = '';
      document.body.removeChild(overlay);
    });
    cancel.onmouseenter = () => { cancel.style.background = '#f3f4f6'; };
    cancel.onmouseleave = () => { cancel.style.background = 'white'; };

    const submit = document.createElement('button');
    submit.type = 'button';
    submit.textContent = '登録';
    submit.className = 'kintoneplugin-button-dialog-ok';
    submit.style.cssText += ';padding:10px 24px;border-radius:8px;font-weight:600;border:none;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:white;cursor:pointer;box-shadow:0 4px 12px rgba(59,130,246,0.4);transition:all 0.2s;';
    submit.addEventListener('click', () => onSubmit(inputs, overlay));
    submit.onmouseenter = () => { submit.style.transform = 'translateY(-2px)'; submit.style.boxShadow = '0 6px 16px rgba(59,130,246,0.5)'; };
    submit.onmouseleave = () => { submit.style.transform = 'translateY(0)'; submit.style.boxShadow = '0 4px 12px rgba(59,130,246,0.4)'; };

    footer.appendChild(cancel);
    footer.appendChild(submit);

    modal.appendChild(header);
    modal.appendChild(form);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    return overlay;
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.right = '20px';
    toast.style.bottom = '20px';
    toast.style.padding = '12px 16px';
    toast.style.borderRadius = '10px';
    toast.style.background = 'rgba(15, 23, 42, 0.92)';
    toast.style.color = '#f8fafc';
    toast.style.boxShadow = '0 12px 30px rgba(15, 23, 42, 0.25)';
    toast.style.fontSize = '14px';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '10001';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    document.body.appendChild(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 220);
    }, 1600);
  }

  function showStyledDialog(message, options) {
    const opts = options || {};
    const kind = opts.kind || 'error';
    const title = opts.title || (kind === 'success' ? '完了' : 'エラー');
    const accent = kind === 'success' ? '#10b981' : '#ef4444';
    const bg = kind === 'success' ? 'linear-gradient(135deg,#ecfdf5,#d1fae5)' : 'linear-gradient(135deg,#fef2f2,#fee2e2)';

    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(2,6,23,0.45);z-index:30000;display:flex;align-items:center;justify-content:center;padding:20px;';

    const modal = document.createElement('div');
    modal.style.cssText = `width:min(520px,92vw);background:white;border-radius:14px;box-shadow:0 20px 50px rgba(2,6,23,0.28);overflow:hidden;border:1px solid #e5e7eb;`;

    const head = document.createElement('div');
    head.style.cssText = `padding:12px 16px;border-bottom:1px solid #e5e7eb;background:${bg};display:flex;align-items:center;justify-content:space-between;gap:8px;`;

    const headTitle = document.createElement('div');
    headTitle.textContent = title;
    headTitle.style.cssText = `font-size:14px;font-weight:700;color:${accent};`;

    const closeX = document.createElement('button');
    closeX.type = 'button';
    closeX.textContent = '×';
    closeX.style.cssText = 'border:none;background:transparent;font-size:20px;line-height:1;color:#6b7280;cursor:pointer;padding:0 4px;';

    const body = document.createElement('div');
    body.style.cssText = 'padding:16px;color:#0f172a;font-size:14px;line-height:1.6;white-space:pre-line;word-break:break-word;max-height:min(55vh,420px);overflow:auto;';
    body.textContent = String(message || '');

    const footer = document.createElement('div');
    footer.style.cssText = 'padding:0 16px 16px;display:flex;justify-content:space-between;align-items:center;gap:10px;';

    const leftActions = document.createElement('div');
    leftActions.style.cssText = 'display:flex;gap:8px;align-items:center;';

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.textContent = 'コピー';
    copyBtn.style.cssText = 'padding:7px 12px;border-radius:8px;border:1px solid #cbd5e1;background:#f8fafc;color:#334155;font-weight:600;cursor:pointer;';
    copyBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText(String(message || ''));
        copyBtn.textContent = 'コピー済み';
        setTimeout(() => {
          copyBtn.textContent = 'コピー';
        }, 1200);
      } catch (e) {
        copyBtn.textContent = 'コピー失敗';
        setTimeout(() => {
          copyBtn.textContent = 'コピー';
        }, 1200);
      }
    };

    const okBtn = document.createElement('button');
    okBtn.type = 'button';
    okBtn.textContent = 'OK';
    okBtn.style.cssText = `padding:8px 18px;border-radius:999px;border:none;background:${accent};color:white;font-weight:700;cursor:pointer;`;

    const detailBtn = document.createElement('button');
    detailBtn.type = 'button';
    detailBtn.textContent = String(opts.detailButtonLabel || '詳細確認');
    detailBtn.style.cssText = 'padding:8px 14px;border-radius:8px;border:1px solid #93c5fd;background:#eff6ff;color:#1d4ed8;font-weight:700;cursor:pointer;';

    const reloadBtn = document.createElement('button');
    reloadBtn.type = 'button';
    reloadBtn.textContent = '再読み込み';
    reloadBtn.style.cssText = 'padding:7px 12px;border-radius:8px;border:1px solid #93c5fd;background:#eff6ff;color:#1d4ed8;font-weight:700;cursor:pointer;';

    const closeDialog = () => {
      if (overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
    };

    closeX.onclick = closeDialog;
    okBtn.onclick = closeDialog;
    detailBtn.onclick = () => {
      closeDialog();
      if (typeof opts.onDetail === 'function') {
        try {
          opts.onDetail();
        } catch (e) {
        }
      }
    };
    reloadBtn.onclick = () => {
      closeDialog();
      setTimeout(() => {
        window.location.assign(window.location.href);
      }, 0);
    };
    overlay.onclick = (event) => {
      if (event.target === overlay) {
        closeDialog();
      }
    };

    head.appendChild(headTitle);
    head.appendChild(closeX);
    leftActions.appendChild(copyBtn);
    if (opts.showReloadButton) {
      leftActions.appendChild(reloadBtn);
    }
    if (typeof opts.onDetail === 'function') {
      leftActions.appendChild(detailBtn);
    }
    footer.appendChild(leftActions);
    footer.appendChild(okBtn);
    modal.appendChild(head);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
  }

  function summarizeUploadError(status, responseText) {
    const text = String(responseText || '').trim();
    const compact = text.replace(/\s+/g, ' ');

    if (compact.includes('CB_CS01') || compact.includes('ページの有効期限')) {
      return `PDFアップロードに失敗しました: セッションの有効期限切れです。ページを再読み込みしてから再実行してください。`;
    }
    if (compact.includes('CB_JH01') || compact.includes('X-Requested-With')) {
      return 'PDFアップロードに失敗しました: セッション認証ヘッダーが不足しています（CB_JH01）。';
    }
    if (compact.includes('このリンクは不正です')) {
      return 'PDFアップロードに失敗しました: 不正なリンクとして扱われました。ページを再読み込みして再実行してください。';
    }
    if (/<html|<body|<head|<div/i.test(compact)) {
      return `PDFアップロードに失敗しました: HTTP ${status}（詳細はHTMLエラーページのため省略）`;
    }

    const shortened = compact.length > 320 ? `${compact.slice(0, 320)}...` : compact;
    return `PDFアップロードに失敗しました: HTTP ${status}${shortened ? ` / ${shortened}` : ''}`;
  }

  function alert(message) {
    const text = String(message || '');
    const needsReload = text.includes('有効期限') || text.includes('CB_CS01') || text.includes('再読み込み');
    showStyledDialog(message, {
      kind: 'error',
      title: 'エラー',
      showReloadButton: needsReload
    });
  }

  function buildRecord(fields, inputs) {
    const record = {};
    Object.keys(fields).forEach((code) => {
      const meta = fields[code];
      const input = inputs[code];
      if (meta.type === 'display') {
        return;
      }
      const value = input.value;
      if (meta.required && !value) {
        throw new Error(meta.label + 'は必須です');
      }
      if (value !== '') {
        record[code] = { value };
      }
    });
    return record;
  }

  function normalizeLabel(value) {
    return String(value || '')
      .replace(/\s+/g, '')
      .replace(/[（]/g, '(')
      .replace(/[）]/g, ')')
      .replace(/[：]/g, ':')
      .replace(/[ー－―]/g, '-');
  }

  function normalizeDigits(value) {
    return String(value || '').replace(/\D/g, '');
  }

  function formatTimeDigits(value) {
    const digits = normalizeDigits(value);
    if (digits.length !== 3 && digits.length !== 4) {
      return null;
    }
    const hourPart = digits.length === 3 ? digits.slice(0, 1) : digits.slice(0, 2);
    const minPart = digits.length === 3 ? digits.slice(1) : digits.slice(2);
    const hour = Number(hourPart);
    const minute = Number(minPart);
    if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
      return null;
    }
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
      return null;
    }
    return `${hour}:${String(minute).padStart(2, '0')}`;
  }

  function bindTimeAutoFormat(input) {
    if (!input) {
      return;
    }
    input.type = 'text';
    input.inputMode = 'numeric';
    input.placeholder = 'HHMM';

    const applyFormat = () => {
      const formatted = formatTimeDigits(input.value);
      if (formatted) {
        input.value = formatted;
      }
    };

    input.addEventListener('input', () => {
      const digits = normalizeDigits(input.value);
      if (digits.length === 3 || digits.length === 4) {
        applyFormat();
      }
    });
    input.addEventListener('blur', applyFormat);
    input.addEventListener('change', applyFormat);
  }

  function applySelectOptions(selectEl, options) {
    if (!selectEl) {
      return;
    }
    const current = selectEl.value;
    selectEl.innerHTML = '';
    (options || []).forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt;
      option.textContent = opt || '選択してください';
      selectEl.appendChild(option);
    });
    if (current && options && options.includes(current)) {
      selectEl.value = current;
    }
  }

  const STAFF_MASTER = {
    appId: CONFIG.apps.workers,
    nameLabel: '氏名'
  };

  let STAFF_OPTIONS = null;

  function fetchStaffOptions() {
    if (STAFF_OPTIONS) {
      return Promise.resolve(STAFF_OPTIONS);
    }
    if (!STAFF_MASTER.appId) {
      return Promise.resolve([]);
    }

    return fetchFormFields(STAFF_MASTER.appId).then((properties) => {
      let nameCode = '';
      Object.keys(properties).forEach((code) => {
        const label = properties[code].label || '';
        if (normalizeLabel(label) === normalizeLabel(STAFF_MASTER.nameLabel)) {
          nameCode = code;
        }
      });
      if (!nameCode) {
        return [];
      }

      return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
        app: STAFF_MASTER.appId,
        fields: [nameCode],
        query: `order by ${nameCode} asc`
      }).then((resp) => {
        const values = (resp.records || [])
          .map((record) => record[nameCode] && record[nameCode].value)
          .filter((value) => value && String(value).trim() !== '');
        STAFF_OPTIONS = Array.from(new Set(values));
        return STAFF_OPTIONS;
      });
    }).catch(() => []);
  }

  const ZIPCODE_API_URL = 'https://zipcloud.ibsnet.co.jp/api/search';

  function normalizeZipcode(zipcode) {
    return String(zipcode || '').replace(/[^\d]/g, '');
  }

  function searchAddressByZipcode(zipcode) {
    const normalized = normalizeZipcode(zipcode);
    if (normalized.length !== 7) {
      return Promise.reject(new Error('invalid_zip'));
    }
    const url = `${ZIPCODE_API_URL}?zipcode=${normalized}`;
    return kintone.proxy(url, 'GET', {}, {}).then((args) => {
      const body = args[0];
      const data = JSON.parse(body);
      if (data.status !== 200 || !data.results || data.results.length === 0) {
        throw new Error('not_found');
      }
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

  function bindPostalAutoFill(postalInput, addressInput) {
    if (!postalInput || !addressInput) {
      return;
    }
    let timer = null;
    let lastNormalized = '';

    const handler = () => {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        const normalized = normalizeZipcode(postalInput.value);
        if (normalized.length !== 7 || normalized === lastNormalized) {
          return;
        }
        lastNormalized = normalized;

        searchAddressByZipcode(normalized)
          .then((result) => {
            const address = `${result.address1}${result.address2}${result.address3}`;
            addressInput.value = address;
            dispatchInputEvents(addressInput);
          })
          .catch(() => {
            // noop
          });
      }, 350);
    };

    postalInput.addEventListener('input', handler);
    postalInput.addEventListener('change', handler);
    postalInput.addEventListener('blur', handler);
  }

  function bindPostalAutoFillToParts(postalInput, prefInput, cityEtcInput) {
    if (!postalInput || !prefInput || !cityEtcInput) {
      return;
    }
    let timer = null;
    let lastNormalized = '';

    const handler = () => {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        const normalized = normalizeZipcode(postalInput.value);
        if (normalized.length !== 7 || normalized === lastNormalized) {
          return;
        }
        lastNormalized = normalized;

        searchAddressByZipcode(normalized)
          .then((result) => {
            prefInput.value = result.address1 || '';
            cityEtcInput.value = `${result.address2 || ''}${result.address3 || ''}`;
            dispatchInputEvents(prefInput);
            dispatchInputEvents(cityEtcInput);
          })
          .catch(() => {
            // noop
          });
      }, 350);
    };

    postalInput.addEventListener('input', handler);
    postalInput.addEventListener('change', handler);
    postalInput.addEventListener('blur', handler);
  }

  function fetchFormFields(appId) {
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/app/form/fields.json`, 'GET', {
      app: appId
    }).then((resp) => resp.properties || {});
  }

  function resolveBillingAppId(kind) {
    const cacheKey = String(kind || '').trim();
    if (!cacheKey) {
      return Promise.reject(new Error('請求/支払アプリ種別が未指定です'));
    }
    if (BILLING_APP_ID_CACHE[cacheKey]) {
      return Promise.resolve(BILLING_APP_ID_CACHE[cacheKey]);
    }

    const configuredId = Number(CONFIG.apps[cacheKey]);
    const candidates = [configuredId]
      .concat(BILLING_APP_ID_CANDIDATES[cacheKey] || [])
      .filter((id, index, array) => Number.isFinite(id) && id > 0 && array.indexOf(id) === index);

    if (!candidates.length) {
      return Promise.reject(new Error(`${cacheKey} のアプリID候補が設定されていません`));
    }

    const tryResolve = (index) => {
      if (index >= candidates.length) {
        const candidateText = candidates.join(', ');
        const current = CONFIG.apps[cacheKey];
        throw new Error(`${cacheKey} アプリが見つかりません。現在値: ${current} / 候補: ${candidateText}`);
      }
      const appId = candidates[index];
      return fetchFormFields(appId)
        .then(() => {
          BILLING_APP_ID_CACHE[cacheKey] = appId;
          CONFIG.apps[cacheKey] = appId;
          return appId;
        })
        .catch(() => tryResolve(index + 1));
    };

    return tryResolve(0);
  }

  function updateRecordsInChunks(appId, records) {
    const queue = Array.isArray(records) ? records.slice() : [];
    if (!queue.length) {
      return Promise.resolve(0);
    }
    const chunkSize = 100;
    let updated = 0;

    const run = () => {
      if (!queue.length) {
        return Promise.resolve(updated);
      }
      const chunk = queue.splice(0, chunkSize);
      return kintone.api(buildQueryPath('records.json'), 'PUT', {
        app: appId,
        records: chunk
      }).then(() => {
        updated += chunk.length;
        return run();
      });
    };

    return run();
  }

  function resolveFieldsByLabel(appId, fields) {
    return fetchFormFields(appId).then((properties) => {
      const labelToCode = {};
      Object.keys(properties).forEach((code) => {
        const label = properties[code].label || '';
        labelToCode[normalizeLabel(label)] = code;
      });

      const resolvedFields = {};
      const sourceToCode = {};
      const missing = [];
      const orderByPreferred = (items, preferredOrder) => {
        const values = (items || []).map((v) => String(v || '').trim()).filter((v) => v !== '');
        const preferred = (preferredOrder || []).map((v) => String(v || '').trim()).filter((v) => v !== '');
        const used = new Set();
        const ordered = [];
        preferred.forEach((name) => {
          const found = values.find((value) => value === name);
          if (found && !used.has(found)) {
            ordered.push(found);
            used.add(found);
          }
        });
        values.forEach((value) => {
          if (!used.has(value)) {
            ordered.push(value);
            used.add(value);
          }
        });
        return ordered;
      };

      Object.keys(fields).forEach((key) => {
        const meta = fields[key];
        const code = labelToCode[normalizeLabel(meta.label)];
        if (!code) {
          missing.push(meta.label);
          return;
        }
        const prop = properties[code] || {};
        const resolvedMeta = Object.assign({}, meta, { sourceKey: key });
        if ((!resolvedMeta.type || resolvedMeta.type === 'select') && (prop.type === 'DROP_DOWN' || prop.type === 'RADIO_BUTTON')) {
          resolvedMeta.type = 'select';
          if (!resolvedMeta.options || resolvedMeta.options.length === 0) {
            resolvedMeta.options = Object.keys(prop.options || {});
          }
          if (appId === CONFIG.apps.vanzai_staff && key === 'role') {
            resolvedMeta.options = orderByPreferred(resolvedMeta.options, ['プレイングマネージャー', '事務', '全体統括', '全体統括責任者']);
          }
        }
        resolvedFields[code] = resolvedMeta;
        sourceToCode[key] = code;
      });

      if (missing.length > 0) {
        console.warn('未検出のフィールドラベル:', missing);
      }

      return { resolvedFields, sourceToCode };
    });
  }

  function resolveFieldsByLabelFlexible(appId, fields) {
    return fetchFormFields(appId).then((properties) => {
      const labelToCode = {};
      const normalizedToCode = {};
      Object.keys(properties).forEach((code) => {
        const label = properties[code].label || '';
        const normalized = normalizeLabel(label);
        labelToCode[label] = code;
        normalizedToCode[normalized] = code;
      });

      const resolvedFields = {};
      const sourceToCode = {};
      const missing = [];
      const orderByPreferred = (items, preferredOrder) => {
        const values = (items || []).map((v) => String(v || '').trim()).filter((v) => v !== '');
        const preferred = (preferredOrder || []).map((v) => String(v || '').trim()).filter((v) => v !== '');
        const used = new Set();
        const ordered = [];
        preferred.forEach((name) => {
          const found = values.find((value) => value === name);
          if (found && !used.has(found)) {
            ordered.push(found);
            used.add(found);
          }
        });
        values.forEach((value) => {
          if (!used.has(value)) {
            ordered.push(value);
            used.add(value);
          }
        });
        return ordered;
      };

      Object.keys(fields).forEach((key) => {
        const meta = fields[key];
        const target = normalizeLabel(meta.label);
        let code = normalizedToCode[target];
        if (!code) {
          code = Object.keys(normalizedToCode).find((normalized) => normalized.includes(target));
          code = code ? normalizedToCode[code] : '';
        }
        if (!code) {
          missing.push(meta.label);
          return;
        }
        const prop = properties[code] || {};
        const resolvedMeta = Object.assign({}, meta, { sourceKey: key });
        if ((!resolvedMeta.type || resolvedMeta.type === 'select') && (prop.type === 'DROP_DOWN' || prop.type === 'RADIO_BUTTON')) {
          resolvedMeta.type = 'select';
          if (!resolvedMeta.options || resolvedMeta.options.length === 0) {
            resolvedMeta.options = Object.keys(prop.options || {});
          }
          if (appId === CONFIG.apps.vanzai_staff && key === 'role') {
            resolvedMeta.options = orderByPreferred(resolvedMeta.options, ['プレイングマネージャー', '事務', '全体統括', '全体統括責任者']);
          }
        }
        resolvedFields[code] = resolvedMeta;
        sourceToCode[key] = code;
      });

      if (missing.length > 0) {
        console.warn('未検出のフィールドラベル:', missing);
      }

      return { resolvedFields, sourceToCode };
    });
  }

  function clearCategoryCache() {
    CATEGORY_DATA = null;
    CATEGORY_OPTIONS = null;
    CATEGORY_RULES = null;
  }

  function setupSitesForm(overlay, sourceToCode) {
    if (!overlay) {
      return;
    }
    const map = sourceToCode || {
      category_major: 'category_major',
      category_middle: 'category_middle',
      category_minor: 'category_minor'
    };
    const majorCode = map.category_major || 'category_major';
    const middleCode = map.category_middle || 'category_middle';
    const minorCode = map.category_minor || 'category_minor';

    setupCategoryCascade(overlay, {
      major: majorCode,
      middle: middleCode,
      minor: minorCode
    });

    const majorSelect = overlay.querySelector(`[data-code="${majorCode}"]`);
    const middleSelect = overlay.querySelector(`[data-code="${middleCode}"]`);
    const minorSelect = overlay.querySelector(`[data-code="${minorCode}"]`);

    const attachAddButton = (fieldCode, onAdd) => {
      const row = overlay.querySelector(`.vanzai-form-row[data-field-code="${fieldCode}"]`);
      const input = overlay.querySelector(`[data-code="${fieldCode}"]`);
      if (!row || !input) {
        return;
      }
      if (row.querySelector('.vanzai-add-category-btn')) {
        return;
      }

      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'display:flex;align-items:center;gap:8px;';
      wrapper.appendChild(input);
      input.style.flex = '1 1 auto';

      const addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'vanzai-add-category-btn';
      addBtn.textContent = '新規カテゴリの追加';
      addBtn.style.cssText = 'flex:0 0 auto;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;';
      addBtn.onclick = onAdd;

      wrapper.appendChild(addBtn);
      row.appendChild(wrapper);
    };

    const refreshCategorySelects = (level, newValue) => {
      clearCategoryCache();
      loadCategoryData().then(() => {
        initCategorySelects(majorSelect, middleSelect, minorSelect);
        if (level === 'major' && majorSelect) {
          majorSelect.value = newValue;
          majorSelect.dispatchEvent(new Event('change', { bubbles: true }));
          return;
        }
        if (level === 'middle' && majorSelect && middleSelect) {
          if (newValue.parentMajor) {
            majorSelect.value = newValue.parentMajor;
            majorSelect.dispatchEvent(new Event('change', { bubbles: true }));
          }
          middleSelect.value = newValue.name;
          middleSelect.dispatchEvent(new Event('change', { bubbles: true }));
          return;
        }
        if (level === 'minor' && majorSelect && middleSelect && minorSelect) {
          if (newValue.parentMajor) {
            majorSelect.value = newValue.parentMajor;
            majorSelect.dispatchEvent(new Event('change', { bubbles: true }));
          }
          if (newValue.parentMiddle) {
            middleSelect.value = newValue.parentMiddle;
            middleSelect.dispatchEvent(new Event('change', { bubbles: true }));
          }
          minorSelect.value = newValue.name;
        }
      }).catch((err) => {
        console.error('カテゴリ再読み込みエラー:', err);
      });
    };

    const createCategoryRecord = (level, name, parentMajor, parentMiddle) => {
      return fetchNextId(CONFIG.apps.project_types, 'type_id', 'PT', 3).then((nextId) => {
        const record = {
          type_id: { value: nextId },
          name: { value: name },
          category_level: { value: level }
        };
        if (parentMajor) {
          record.parent_major = { value: parentMajor };
        }
        if (parentMiddle) {
          record.parent_middle = { value: parentMiddle };
        }
        return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/record.json`, 'POST', {
          app: CONFIG.apps.project_types,
          record
        });
      });
    };

    attachAddButton(majorCode, () => {
      const name = String(window.prompt('追加する大カテゴリ名を入力してください', '') || '').trim();
      if (!name) {
        return;
      }
      createCategoryRecord('major', name, '', '').then(() => {
        showToast('大カテゴリを追加しました');
        refreshCategorySelects('major', name);
      }).catch((err) => {
        alert('大カテゴリの追加に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
      });
    });

    attachAddButton(middleCode, () => {
      const parentMajor = majorSelect ? String(majorSelect.value || '').trim() : '';
      if (!parentMajor) {
        alert('先に大カテゴリを選択してください');
        return;
      }
      const name = String(window.prompt('追加する中カテゴリ名を入力してください', '') || '').trim();
      if (!name) {
        return;
      }
      createCategoryRecord('middle', name, parentMajor, '').then(() => {
        showToast('中カテゴリを追加しました');
        refreshCategorySelects('middle', { name, parentMajor });
      }).catch((err) => {
        alert('中カテゴリの追加に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
      });
    });

    attachAddButton(minorCode, () => {
      const parentMajor = majorSelect ? String(majorSelect.value || '').trim() : '';
      const parentMiddle = middleSelect ? String(middleSelect.value || '').trim() : '';
      if (!parentMiddle) {
        alert('先に中カテゴリを選択してください');
        return;
      }
      const name = String(window.prompt('追加する小カテゴリ名を入力してください', '') || '').trim();
      if (!name) {
        return;
      }
      createCategoryRecord('minor', name, parentMajor, parentMiddle).then(() => {
        showToast('小カテゴリを追加しました');
        refreshCategorySelects('minor', { name, parentMajor, parentMiddle });
      }).catch((err) => {
        alert('小カテゴリの追加に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
      });
    });
  }

  function setupCategoryCascade(overlay, fieldCodes) {
    if (!fieldCodes) {
      return;
    }
    const majorSelect = overlay.querySelector(`[data-code="${fieldCodes.major}"]`);
    const middleSelect = overlay.querySelector(`[data-code="${fieldCodes.middle}"]`);
    const minorSelect = overlay.querySelector(`[data-code="${fieldCodes.minor}"]`);

    loadCategoryData().then(() => {
      initCategorySelects(majorSelect, middleSelect, minorSelect);
    }).catch((err) => {
      console.error('カテゴリマスタ読み込みエラー:', err);
    });

    const applyOptions = (selectEl, options) => {
      if (!selectEl) {
        return;
      }
      const current = selectEl.value;
      selectEl.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '選択してください';
      selectEl.appendChild(emptyOption);
      (options || []).forEach((opt) => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        selectEl.appendChild(option);
      });
      if (current && options && options.includes(current)) {
        selectEl.value = current;
      }
    };

    const updateMiddleOptions = () => {
      if (!majorSelect || !middleSelect || !CATEGORY_RULES) {
        return;
      }
      const majorValue = majorSelect.value;
      let options = CATEGORY_RULES.majorToMiddle[majorValue] || [];
      if (options.length === 0 && CATEGORY_OPTIONS && CATEGORY_OPTIONS.middle) {
        options = CATEGORY_OPTIONS.middle.filter((value) => value !== '');
      }
      applyOptions(middleSelect, options);
      updateMinorOptions();
    };

    const updateMinorOptions = () => {
      if (!minorSelect || !middleSelect || !CATEGORY_RULES) {
        return;
      }
      const middleValue = middleSelect.value;
      const middleKey = String(middleValue || '').trim().replace(/[：:]/g, '');
      const options = CATEGORY_RULES.middleToMinor[middleKey] || [];
      applyOptions(minorSelect, options);
    };

    if (majorSelect) {
      majorSelect.addEventListener('change', updateMiddleOptions);
    }
    if (middleSelect) {
      middleSelect.addEventListener('change', updateMinorOptions);
    }

    updateMiddleOptions();
  }

  function fetchLastRecordNumber(appId) {
    const query = 'order by $id desc limit 1';
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query,
      fields: ['$id']
    }).then((resp) => {
      const records = resp.records || [];
      if (records.length === 0) {
        return 0;
      }
      const lastId = records[0].$id && records[0].$id.value ? Number(records[0].$id.value) : 0;
      return Number.isFinite(lastId) ? lastId : 0;
    }).catch(() => 0);
  }

  function fetchNextId(appId, fieldCode, prefix, width) {
    console.log('[DEBUG fetchNextId] appId:', appId, 'fieldCode:', fieldCode, 'prefix:', prefix);
    const query = `${fieldCode} like "${prefix}%" order by ${fieldCode} desc limit 1`;
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query,
      fields: [fieldCode]
    }).then((resp) => {
      const records = resp.records || [];
      console.log('[DEBUG fetchNextId] 取得レコード数:', records.length);
      if (records.length === 0) {
        return fetchLastRecordNumber(appId).then((lastId) => {
          const nextNum = Number(lastId) + 1 || 1;
          return `${prefix}${String(nextNum).padStart(width, '0')}`;
        });
      }
      const lastValue = records[0][fieldCode].value || '';
      const suffix = lastValue.replace(prefix, '');
      const nextNum = Number(suffix) + 1 || 1;
      return `${prefix}${String(nextNum).padStart(width, '0')}`;
    }).catch((err) => {
      console.error('[ERROR fetchNextId] 詳細:', err);
      console.error('[ERROR fetchNextId] メッセージ:', err.message);
      console.error('[ERROR fetchNextId] レスポンス:', JSON.stringify(err));
      return fetchLastRecordNumber(appId).then((lastId) => {
        const nextNum = Number(lastId) + 1 || 1;
        return `${prefix}${String(nextNum).padStart(width, '0')}`;
      });
    });
  }

  let ASSIGNMENT_LIST_CACHE = null;
  let ASSIGNMENT_LIST_FILTER = 'all';
  let ASSIGNMENT_LIST_ACTUALS_FILTER = 'all';
  let ASSIGNMENT_LIST_SORT = { column: 'assignment_id', direction: 'desc' };
  let STAFF_MANAGERS_CACHE = null;
  let WORKERS_CACHE = null;
  let WORKERS_ALL_CACHE = null;
  let VANZAI_STAFF_CACHE = null;
  let SUPPLIERS_CACHE = null;
  let CLIENTS_CACHE = null;
  let WORKER_LIST_FILTER = 'all';
  let WORKER_FIELD_CODES_CACHE = null;
  let ACTUAL_WORKER_IDS_BY_PERIOD_CACHE = {};
  let ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE = {};
  let ACTUALS_FIELD_CODES_CACHE = null;
  let INVOICE_FIELD_CODES_CACHE = null;
  let PAYOUT_FIELD_CODES_CACHE = null;
  const BILLING_APP_ID_CACHE = {};
  const BILLING_APP_ID_CANDIDATES = {
    invoices: [171, 169, 9],
    payouts: [173, 170, 10]
  };

  function getWorkerDisplayName(record) {
    if (!record) {
      return '';
    }
    const lastNameCode = WORKER_FIELD_CODES_CACHE && WORKER_FIELD_CODES_CACHE.lastNameCode
      ? WORKER_FIELD_CODES_CACHE.lastNameCode
      : 'last_name';
    const firstNameCode = WORKER_FIELD_CODES_CACHE && WORKER_FIELD_CODES_CACHE.firstNameCode
      ? WORKER_FIELD_CODES_CACHE.firstNameCode
      : 'first_name';
    const fullNameCode = WORKER_FIELD_CODES_CACHE && WORKER_FIELD_CODES_CACHE.fullNameCode
      ? WORKER_FIELD_CODES_CACHE.fullNameCode
      : 'name';
    const lastName = getFieldValue(record, lastNameCode) || getFieldValue(record, 'last_name');
    const firstName = getFieldValue(record, firstNameCode) || getFieldValue(record, 'first_name');
    const fullName = `${lastName} ${firstName}`.trim();
    if (fullName) {
      return fullName;
    }

    const directCandidates = [
      getFieldValue(record, fullNameCode),
      getFieldValue(record, 'name'),
      getFieldValue(record, 'worker_name'),
      getFieldValue(record, 'full_name'),
      getFieldValue(record, 'employee_name'),
      getFieldValue(record, 'staff_name')
    ].map((v) => String(v || '').trim()).filter(Boolean);
    if (directCandidates.length > 0) {
      return directCandidates[0];
    }

    const isLikelyNameCode = (code) => {
      const c = String(code || '').toLowerCase();
      if (!c) {
        return false;
      }
      if (c.includes('name') || c.includes('namae') || c.includes('full') || c.includes('first') || c.includes('last') || c.includes('surname') || c.includes('given') || c.includes('sei') || c.includes('mei')) {
        return true;
      }
      return false;
    };

    let looseLast = '';
    let looseFirst = '';
    const looseSingles = [];
    Object.keys(record || {}).forEach((code) => {
      const value = getFieldValue(record, code).trim();
      if (!value) {
        return;
      }
      if (!isLikelyNameCode(code)) {
        return;
      }
      const lc = String(code || '').toLowerCase();
      if (!looseLast && (lc.includes('last') || lc.includes('surname') || lc.includes('sei'))) {
        looseLast = value;
        return;
      }
      if (!looseFirst && (lc.includes('first') || lc.includes('given') || lc.includes('mei'))) {
        looseFirst = value;
        return;
      }
      looseSingles.push(value);
    });

    const looseFull = `${looseLast} ${looseFirst}`.trim();
    if (looseFull) {
      return looseFull;
    }
    if (looseSingles.length > 0) {
      return looseSingles[0];
    }

    const workerIdFallback = getFieldValue(record, 'worker_id').trim();
    if (workerIdFallback) {
      return workerIdFallback;
    }

    return '';
  }

  function getWorkerLastNameKana(record) {
    if (!record) {
      return '';
    }
    if (record.lastname_furigana && record.lastname_furigana.value) {
      return String(record.lastname_furigana.value).trim();
    }
    if (record.last_name && record.last_name.value) {
      return String(record.last_name.value).trim();
    }
    return getWorkerDisplayName(record).trim();
  }

  function sortWorkersByLastNameKana(records) {
    return (Array.isArray(records) ? records.slice() : []).sort((a, b) => {
      const aKana = getWorkerLastNameKana(a);
      const bKana = getWorkerLastNameKana(b);
      const kanaCompare = aKana.localeCompare(bKana, 'ja');
      if (kanaCompare !== 0) {
        return kanaCompare;
      }
      const aName = getWorkerDisplayName(a);
      const bName = getWorkerDisplayName(b);
      const nameCompare = aName.localeCompare(bName, 'ja');
      if (nameCompare !== 0) {
        return nameCompare;
      }
      const aId = a && a.worker_id && a.worker_id.value ? String(a.worker_id.value).trim() : '';
      const bId = b && b.worker_id && b.worker_id.value ? String(b.worker_id.value).trim() : '';
      return aId.localeCompare(bId, 'ja');
    });
  }

  function getWorkerGroup(record) {
    if (!record) {
      return '';
    }
    const viaCode = WORKER_FIELD_CODES_CACHE && WORKER_FIELD_CODES_CACHE.viaCode
      ? WORKER_FIELD_CODES_CACHE.viaCode
      : 'via_destination';
    return getFieldValue(record, viaCode)
      || getFieldValue(record, 'via_destination')
      || getFieldValue(record, 'group')
      || '';
  }

  function getWorkerIntroducer(record) {
    if (!record) {
      return '';
    }
    const introducerCode = WORKER_FIELD_CODES_CACHE && WORKER_FIELD_CODES_CACHE.introducerCode
      ? WORKER_FIELD_CODES_CACHE.introducerCode
      : 'introducer_supplier';
    return getFieldValue(record, introducerCode)
      || getFieldValue(record, 'introducer_supplier')
      || getFieldValue(record, 'introducer_supplier_id')
      || '';
  }

  function normalizeViaDestination(value) {
    const raw = String(value || '').trim();
    if (!raw) {
      return '';
    }
    if (raw === 'VANZAI直接' || raw === 'VANZAI' || raw === 'VANZAI直契約') {
      return 'VANZAI直接';
    }
    if (raw.includes('紹介')) {
      return '紹介';
    }
    if (raw.includes('下請け')) {
      return '下請け';
    }
    return raw;
  }

  function isDirectViaDestination(value) {
    return normalizeViaDestination(value) === 'VANZAI直接';
  }

  async function fetchRecordsByPages(appId, baseQuery, fields) {
    const limit = 500;
    const maxPages = 20;
    const all = [];
    for (let page = 0; page < maxPages; page += 1) {
      const offset = page * limit;
      const query = `${baseQuery} limit ${limit} offset ${offset}`;
      const params = { app: appId, query };
      if (fields && fields.length) {
        params.fields = fields;
      }
      const resp = await kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', params);
      const records = resp && resp.records ? resp.records : [];
      all.push.apply(all, records);
      if (records.length < limit) {
        break;
      }
    }
    return all;
  }

  function fetchWorkers() {
    if (WORKERS_CACHE) {
      return Promise.resolve(WORKERS_CACHE);
    }
    return resolveWorkerFieldCodes().catch(() => ({ viaCode: 'via_destination', introducerCode: 'introducer_supplier' })).then(() => {
      const appId = CONFIG.apps.workers;
      const baseQuery = 'is_active in ("有効") order by worker_id asc';
      return fetchRecordsByPages(appId, baseQuery).then((records) => {
        WORKERS_CACHE = records || [];
        return WORKERS_CACHE;
      }).catch(() => {
        return fetchRecordsByPages(appId, 'order by worker_id asc').then((records) => {
          WORKERS_CACHE = records || [];
          return WORKERS_CACHE;
        }).catch(() => []);
      });
    });
  }

  function fetchAllWorkers() {
    if (WORKERS_ALL_CACHE) {
      return Promise.resolve(WORKERS_ALL_CACHE);
    }
    return resolveWorkerFieldCodes().catch(() => ({ viaCode: 'via_destination', introducerCode: 'introducer_supplier' })).then(() => {
      const appId = CONFIG.apps.workers;
      // worker_id でソートを試みて失敗したら $id でソートするフォールバック
      return fetchRecordsByPages(appId, 'order by worker_id asc').catch(() => {
        console.warn('[fetchAllWorkers] worker_idソート失敗: $idでリトライ');
        return fetchRecordsByPages(appId, 'order by $id asc');
      }).then((records) => {
        WORKERS_ALL_CACHE = records || [];
        console.log('[fetchAllWorkers] App165取得件数:', WORKERS_ALL_CACHE.length);
        if (WORKERS_ALL_CACHE.length > 0) {
          // 先頭レコードのworker_idを確認
          const sample = WORKERS_ALL_CACHE[0];
          const sampleId = sample && sample.worker_id && sample.worker_id.value ? String(sample.worker_id.value) : '(worker_idフィールドなし)';
          console.log('[fetchAllWorkers] 先頭レコードworker_id:', sampleId, '全フィールド:', Object.keys(sample || {}));
        }
        return WORKERS_ALL_CACHE;
      }).catch((err) => {
        console.error('稼働者一覧取得エラー(fetchAllWorkers):', err);
        return [];
      });
    });
  }

  function fetchVanzaiStaffs() {
    if (VANZAI_STAFF_CACHE) {
      return Promise.resolve(VANZAI_STAFF_CACHE);
    }
    const appId = CONFIG.apps.vanzai_staff;
    if (!appId) {
      return Promise.resolve([]);
    }
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query: 'order by id asc limit 500'
    }).then((resp) => {
      VANZAI_STAFF_CACHE = resp.records || [];
      return VANZAI_STAFF_CACHE;
    }).catch((err) => {
      console.error('VANZAI職員一覧取得エラー:', err);
      return [];
    });
  }

  function fetchSuppliers() {
    if (SUPPLIERS_CACHE) {
      return Promise.resolve(SUPPLIERS_CACHE);
    }
    const appId = CONFIG.apps.suppliers;
    const query = 'is_active in ("有効") order by supplier_id asc limit 500';
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query
    }).then((resp) => {
      SUPPLIERS_CACHE = resp.records || [];
      return SUPPLIERS_CACHE;
    }).catch(() => []);
  }

  function fetchClients() {
    if (CLIENTS_CACHE) {
      return Promise.resolve(CLIENTS_CACHE);
    }
    const appId = CONFIG.apps.clients;
    const query = 'limit 500';
    console.log('[DEBUG fetchClients] appId:', appId, 'query:', query);
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query
    }).then((resp) => {
      console.log('[DEBUG fetchClients] 成功:', resp);
      CLIENTS_CACHE = resp.records || [];
      return CLIENTS_CACHE;
    }).catch((err) => {
      console.error('[ERROR fetchClients] 詳細:', err);
      console.error('[ERROR fetchClients] メッセージ:', err.message);
      console.error('[ERROR fetchClients] レスポンス:', JSON.stringify(err));
      return [];
    });
  }
  function fetchAssignmentList() {
    if (ASSIGNMENT_LIST_CACHE) {
      return Promise.resolve(ASSIGNMENT_LIST_CACHE);
    }
    const appId = CONFIG.apps.project_assignments;
    const fields = [
      '$id',
      'assignment_id',
      'assignment_title',
      'sales_flag',
      'facility_name',
      'event_name',
      'start_date',
      'company_name',
      'owner_name',
      'main_staff',
      'playing_manager',
      'director',
      'assistant_director',
      'field_staff',
      'headcount_required',
      'headcount_director',
      'headcount_staff',
      'address',
      'work_hours',
      'base_reward',
      'base_reward_director',
      'base_reward_assistant_director',
      'base_reward_staff',
      'incentive',
      'category_major',
      'category_middle',
      'category_minor',
      'gathering_time',
      'start_time',
      'end_time',
      'dismissal_time'
    ];
    const query = 'order by assignment_id desc limit 500';
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      fields,
      query
    }).then((resp) => {
      ASSIGNMENT_LIST_CACHE = resp.records || [];
      return ASSIGNMENT_LIST_CACHE;
    });
  }

  function fetchStaffManagers() {
    if (STAFF_MANAGERS_CACHE) {
      return Promise.resolve(STAFF_MANAGERS_CACHE);
    }
    const appId = CONFIG.apps.staff_managers;
    const query = 'limit 500';
    console.log('[DEBUG fetchStaffManagers] appId:', appId, 'query:', query);
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query
    }).then((resp) => {
      console.log('[DEBUG fetchStaffManagers] 成功:', resp);
      STAFF_MANAGERS_CACHE = resp.records || [];
      return STAFF_MANAGERS_CACHE;
    }).catch((err) => {
      console.error('[ERROR fetchStaffManagers] 詳細:', err);
      console.error('[ERROR fetchStaffManagers] メッセージ:', err.message);
      console.error('[ERROR fetchStaffManagers] レスポンス:', JSON.stringify(err));
      return [];
    });
  }

  let ACTUALS_ASSIGNMENT_IDS_CACHE = null;
  function fetchActualAssignmentIds() {
    if (ACTUALS_ASSIGNMENT_IDS_CACHE) {
      return Promise.resolve(ACTUALS_ASSIGNMENT_IDS_CACHE);
    }
    const appId = CONFIG.apps.actuals;
    const query = 'order by assignment_id desc limit 500';
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: appId,
      query,
      fields: ['assignment_id']
    }).then((resp) => {
      const records = resp.records || [];
      const ids = new Set();
      records.forEach((r) => {
        const v = r.assignment_id && r.assignment_id.value ? String(r.assignment_id.value).trim() : '';
        if (v) {
          ids.add(v);
        }
      });
      ACTUALS_ASSIGNMENT_IDS_CACHE = ids;
      return ids;
    }).catch(() => new Set());
  }

  function getFieldValue(record, code) {
    if (!record || !code || !record[code]) {
      return '';
    }
    return record[code] && record[code].value ? String(record[code].value) : '';
  }

  function findWorkerRecordByIdentity(records, workerIdentity) {
    const target = String(workerIdentity || '').trim();
    if (!target || !Array.isArray(records) || records.length === 0) {
      return null;
    }

    const normalizeIdentity = (value) => String(value || '').trim();
    const normalizeIdentityLower = (value) => normalizeIdentity(value).toLowerCase();
    const normalizeIdentityAlnum = (value) => normalizeIdentityLower(value).replace(/[^a-z0-9]/g, '');
    const targetRaw = normalizeIdentity(target);
    const targetLower = normalizeIdentityLower(target);
    const targetAlnum = normalizeIdentityAlnum(target);

    const matchesValue = (value) => {
      const normalized = normalizeIdentity(value);
      if (!normalized) {
        return false;
      }
      if (normalized === targetRaw) {
        return true;
      }
      const lower = normalizeIdentityLower(normalized);
      if (lower === targetLower) {
        return true;
      }
      const alnum = normalizeIdentityAlnum(normalized);
      return !!(targetAlnum && alnum && alnum === targetAlnum);
    };

    for (let i = 0; i < records.length; i += 1) {
      const record = records[i];
      if (!record) {
        continue;
      }

      if (record.$id && matchesValue(record.$id.value)) {
        return record;
      }

      const keys = Object.keys(record);
      for (let j = 0; j < keys.length; j += 1) {
        const key = keys[j];
        const cell = record[key];
        if (!cell || typeof cell !== 'object' || !Object.prototype.hasOwnProperty.call(cell, 'value')) {
          continue;
        }
        const value = cell.value;
        if (Array.isArray(value)) {
          for (let k = 0; k < value.length; k += 1) {
            if (matchesValue(value[k])) {
              return record;
            }
          }
        } else if (matchesValue(value)) {
          return record;
        }
      }
    }

    return null;
  }

  function isKnownCandidate(code, candidates) {
    if (!code || !candidates || !candidates.length) {
      return false;
    }
    const lower = String(code).toLowerCase();
    return candidates.some((candidate) => lower === String(candidate).toLowerCase());
  }

  function findFieldCode(properties, exactCandidates, labelCandidates, typeFilter) {
    const keys = Object.keys(properties || {});
    if (!keys.length) {
      return '';
    }

    for (let i = 0; i < keys.length; i += 1) {
      const code = keys[i];
      const prop = properties[code];
      if (typeFilter && prop.type !== typeFilter) {
        continue;
      }
      if (isKnownCandidate(code, exactCandidates)) {
        return code;
      }
    }

    const normalizedLabelCandidates = (labelCandidates || []).map((v) => normalizeLabel(v));
    for (let i = 0; i < keys.length; i += 1) {
      const code = keys[i];
      const prop = properties[code];
      if (typeFilter && prop.type !== typeFilter) {
        continue;
      }
      const label = normalizeLabel(prop.label || '');
      if (normalizedLabelCandidates.some((cand) => label.includes(cand))) {
        return code;
      }
    }

    return '';
  }

  function toPeriodKey(year, month) {
    return `${year}${String(month).padStart(2, '0')}`;
  }

  function toMonthRange(year, month) {
    const from = new Date(year, month - 1, 1);
    const to = new Date(year, month, 0);
    const fromIso = `${from.getFullYear()}-${String(from.getMonth() + 1).padStart(2, '0')}-${String(from.getDate()).padStart(2, '0')}`;
    const toIso = `${to.getFullYear()}-${String(to.getMonth() + 1).padStart(2, '0')}-${String(to.getDate()).padStart(2, '0')}`;
    return { from: fromIso, to: toIso };
  }

  function parsePeriodKey(periodKey) {
    const key = String(periodKey || '').trim();
    if (!/^\d{6}$/.test(key)) {
      return null;
    }
    const year = Number(key.slice(0, 4));
    const month = Number(key.slice(4, 6));
    if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) {
      return null;
    }
    return { year, month };
  }

  function formatDateYmd(dateObj) {
    if (!(dateObj instanceof Date) || Number.isNaN(dateObj.getTime())) {
      return '';
    }
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const d = String(dateObj.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function computePayoutCloseDate(periodKey) {
    const parsed = parsePeriodKey(periodKey);
    if (!parsed) {
      return '';
    }
    return formatDateYmd(new Date(parsed.year, parsed.month - 1, 0));
  }

  function computePayoutPaymentDate(periodKey) {
    const parsed = parsePeriodKey(periodKey);
    if (!parsed) {
      return '';
    }
    const base = new Date(parsed.year, parsed.month + 1, 0);
    while (base.getDay() === 0 || base.getDay() === 6) {
      base.setDate(base.getDate() + 1);
    }
    const month = base.getMonth() + 1;
    const date = base.getDate();
    if (month === 1 && date <= 3) {
      base.setDate(4);
      while (base.getDay() === 0 || base.getDay() === 6) {
        base.setDate(base.getDate() + 1);
      }
    }
    return formatDateYmd(base);
  }

  function extractAreaName(address) {
    const raw = String(address || '').trim();
    if (!raw) {
      return 'その他';
    }
    if (raw.includes('東京')) {
      return '東京';
    }
    if (raw.includes('神奈川')) {
      return '神奈川';
    }
    if (raw.includes('埼玉')) {
      return '埼玉';
    }
    if (raw.includes('千葉')) {
      return '千葉';
    }
    return 'その他';
  }

  async function buildInvoiceLineItems(periodKey, responsible, fixedOfficeFeeNum, clientCompany) {
    const parsed = parsePeriodKey(periodKey);
    if (!parsed) {
      return [];
    }
    const selectedClientCompany = String(clientCompany || '').trim();

    const assignments = await fetchAssignmentList();
    const targetRecords = (assignments || []).filter((record) => {
      const owner = getFieldValue(record, 'owner_name').trim();
      if (owner && String(responsible || '').trim() && owner !== String(responsible || '').trim()) {
        return false;
      }
      if (selectedClientCompany) {
        const company = getFieldValue(record, 'company_name').trim();
        if (!company || company !== selectedClientCompany) {
          return false;
        }
      }
      const start = getFieldValue(record, 'start_date').trim();
      if (!start || start.length < 7) {
        return false;
      }
      const y = Number(start.slice(0, 4));
      const m = Number(start.slice(5, 7));
      return y === parsed.year && m === parsed.month;
    });

    const lineItems = [];
    const sortedRecords = targetRecords.slice().sort((a, b) => {
      const aDate = getFieldValue(a, 'start_date');
      const bDate = getFieldValue(b, 'start_date');
      return String(aDate).localeCompare(String(bDate), 'ja');
    });

    sortedRecords.forEach((record) => {
      const amount = Math.max(parseAmountNumber(getFieldValue(record, 'base_reward')), 0);
      if (amount <= 0) {
        return;
      }
      const area = extractAreaName(getFieldValue(record, 'address'));
      const titleRaw = getFieldValue(record, 'assignment_title')
        || getFieldValue(record, 'project_name')
        || getFieldValue(record, 'event_name')
        || getFieldValue(record, 'facility_name')
        || '稼働人工';
      const title = String(titleRaw).replace(/\s+/g, ' ').trim().slice(0, 14);
      const itemName = `${area}_${title || '稼働人工'}`;
      lineItems.push({ name: itemName, quantity: '一式', unitPrice: amount, amount });
    });

    if (fixedOfficeFeeNum > 0) {
      lineItems.push({ name: '固定事務局費', quantity: '一式', unitPrice: fixedOfficeFeeNum, amount: fixedOfficeFeeNum });
    }

    return lineItems;
  }

  async function resolveInvoiceAddressee(periodKey, responsible, clientCompany) {
    const responsibleName = String(responsible || '').trim();
    if (!responsibleName) {
      return '-';
    }

    let clientName = String(clientCompany || '').trim();

    try {
      const staffManagers = await fetchStaffManagers();
      const matched = (staffManagers || []).find((record) => {
        const name = getFieldValue(record, 'name').trim();
        return name === responsibleName;
      });
      if (matched) {
        clientName = getFieldValue(matched, 'client_company').trim()
          || getFieldValue(matched, 'cliant_company').trim()
          || getFieldValue(matched, 'client_name').trim();
      }
    } catch (e) {
    }

    if (!clientName) {
      try {
        const parsed = parsePeriodKey(periodKey);
        const assignments = await fetchAssignmentList();
        const filtered = (assignments || []).filter((record) => {
          const owner = getFieldValue(record, 'owner_name').trim();
          if (owner !== responsibleName) {
            return false;
          }
          if (!parsed) {
            return true;
          }
          const start = getFieldValue(record, 'start_date').trim();
          if (!start || start.length < 7) {
            return false;
          }
          const y = Number(start.slice(0, 4));
          const m = Number(start.slice(5, 7));
          return y === parsed.year && m === parsed.month;
        });
        if (filtered.length) {
          const counts = new Map();
          filtered.forEach((record) => {
            const company = getFieldValue(record, 'company_name').trim();
            if (company) {
              counts.set(company, (counts.get(company) || 0) + 1);
            }
          });
          clientName = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0]?.[0] || '';
        }
      } catch (e) {
      }
    }

    const addressee = [clientName, responsibleName].filter(Boolean).join(' ').trim();
    return addressee ? `${addressee} 様` : `${responsibleName} 様`;
  }

  function buildQueryPath(resource) {
    return GUEST_SPACE_ID ? `/k/guest/${GUEST_SPACE_ID}/v1/${resource}` : `/k/v1/${resource}`;
  }

  function sanitizeFileName(name) {
    return String(name || '')
      .replace(/[\\/:*?"<>|]/g, '_')
      .replace(/\s+/g, '_')
      .slice(0, 120);
  }

  function escapeKintoneQueryValue(value) {
    return String(value || '')
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"');
  }

  function buildKintoneFieldCondition(fieldCode, fieldType, value) {
    if (!fieldCode) {
      return '';
    }
    const escaped = escapeKintoneQueryValue(value);
    const setOperatorTypes = ['CHECK_BOX', 'MULTI_SELECT', 'CATEGORY', 'USER_SELECT', 'ORGANIZATION_SELECT', 'GROUP_SELECT', 'STATUS_ASSIGNEE', 'DROP_DOWN', 'RADIO_BUTTON'];
    if (setOperatorTypes.includes(fieldType)) {
      return `${fieldCode} in ("${escaped}")`;
    }
    return `${fieldCode} = "${escaped}"`;
  }

  function fetchRecords(appId, query, fields) {
    const params = {
      app: appId,
      query,
    };
    if (fields && fields.length) {
      params.fields = fields;
    }
    return kintone.api(buildQueryPath('records.json'), 'GET', params)
      .then((resp) => resp.records || []);
  }

  function resolveActualsFieldCodes() {
    if (ACTUALS_FIELD_CODES_CACHE) {
      return Promise.resolve(ACTUALS_FIELD_CODES_CACHE);
    }
    return fetchFormFields(CONFIG.apps.actuals).then((properties) => {
      console.log('[resolveActualsFieldCodes] 実績アプリ全フィールドコード:', Object.keys(properties || {}));
      const workerCode = (properties && properties.worker_id)
        ? 'worker_id'
        : (findFieldCode(
          properties,
          ['worker_id'],
          ['稼働者ID', '稼働者'],
          ''
        ) || 'worker_id');
      const dateCode = findFieldCode(
        properties,
        ['work_date', 'date'],
        ['稼働日', 'シフト日', '日付'],
        'DATE'
      ) || 'work_date';
      const workerNameCode = findFieldCode(
        properties,
        ['worker_name', 'name', 'worker_full_name', 'full_name', 'staff_name', 'member_name', 'employee_name', 'last_name', '氏名'],
        ['稼働者名', '氏名', '名前', '社員名', 'スタッフ名'],
        ''
      ) || '';
      const lastNameCode = findFieldCode(properties, ['last_name', 'lastname', 'sei', 'family_name'], ['姓', '氏名(姓)'], '') || '';
      const firstNameCode = findFieldCode(properties, ['first_name', 'firstname', 'mei', 'given_name'], ['名', '氏名(名)'], '') || '';
      const workerType = (properties[workerCode] && properties[workerCode].type) ? properties[workerCode].type : '';
      const dateType = (properties[dateCode] && properties[dateCode].type) ? properties[dateCode].type : '';

      // DROP_DOWN型の worker_id の場合、options から ULID→表示名マップを構築する
      // kintone DROP_DOWN options: { "ULID値": { label: "表示名", index: N } }
      // kintoneはkey=labelの制約があるため、WORKER_ULID_MAP静的定数でフォールバック補完する
      const workerIdOptions = (properties[workerCode] && properties[workerCode].options) ? properties[workerCode].options : null;
      const workerIdLabelMap = {};
      // まず WORKER_ULID_MAP をベースとして全件登録（静的フォールバック）
      Object.assign(workerIdLabelMap, WORKER_ULID_MAP);
      if (workerIdOptions) {
        Object.keys(workerIdOptions).forEach((key) => {
          const label = workerIdOptions[key] && workerIdOptions[key].label ? String(workerIdOptions[key].label).trim() : '';
          // kintoneのlabelがkeyと異なる場合のみ上書き（= 正しい氏名が設定されている場合）
          if (key && label && label !== key) {
            workerIdLabelMap[key] = label;
          }
        });
        console.log('[resolveActualsFieldCodes] worker_id DROP_DOWNオプション数:', Object.keys(workerIdOptions).length, '有効label数:', Object.keys(workerIdLabelMap).length, 'サンプル:', Object.entries(workerIdLabelMap).slice(0, 3));
      } else {
        console.log('[resolveActualsFieldCodes] worker_id options未取得、WORKER_ULID_MAP静的フォールバック使用:', Object.keys(workerIdLabelMap).length, '件');
      }

      console.log('[resolveActualsFieldCodes]', { workerCode, workerType, workerNameCode, lastNameCode, firstNameCode, dropdownMapSize: Object.keys(workerIdLabelMap).length });
      ACTUALS_FIELD_CODES_CACHE = { workerCode, workerType, dateCode, dateType, workerNameCode, lastNameCode, firstNameCode, workerIdLabelMap };
      return ACTUALS_FIELD_CODES_CACHE;
    });
  }

  function resolveInvoiceFieldCodes() {
    if (INVOICE_FIELD_CODES_CACHE) {
      return Promise.resolve(INVOICE_FIELD_CODES_CACHE);
    }
    return resolveBillingAppId('invoices').then((invoiceAppId) => fetchFormFields(invoiceAppId).then((properties) => {
      const periodCode = findFieldCode(
        properties,
        ['period_key'],
        ['期間', '対象月', '年月'],
        ''
      ) || 'period_key';
      const periodType = (properties[periodCode] && properties[periodCode].type) ? properties[periodCode].type : '';
      const typeCode = findFieldCode(
        properties,
        ['document_type', 'invoice_type', 'doc_type'],
        ['見積', '請求書種別', '帳票種別'],
        ''
      );
      const typeFieldType = typeCode && properties[typeCode] ? properties[typeCode].type : '';
      const ownerCode = findFieldCode(
        properties,
        ['owner_name', 'responsible_name', 'client_manager'],
        ['責任者', '担当者'],
        ''
      );
      const ownerFieldType = ownerCode && properties[ownerCode] ? properties[ownerCode].type : '';
      const clientCompanyCode = findFieldCode(
        properties,
        ['client_company', 'company_name', 'client_name', 'billing_company'],
        ['クライアント', '会社名', '請求先'],
        ''
      );
      const clientCompanyFieldType = clientCompanyCode && properties[clientCompanyCode] ? properties[clientCompanyCode].type : '';
      const subjectCode = findFieldCode(
        properties,
        ['subject', 'subject_manual', 'title'],
        ['件名', 'タイトル'],
        ''
      );
      const fixedOfficeFeeCode = findFieldCode(
        properties,
        ['fixed_office_fee', 'office_fee', 'admin_fee', 'secretariat_fee', 'fixed_admin_fee'],
        ['固定事務局費', '事務局費', '固定管理費', '管理費'],
        ''
      );
      const invoiceIdCode = findFieldCode(
        properties,
        ['invoice_id', 'id'],
        ['請求書ID', '見積書ID', 'ID'],
        ''
      );
      const pdfUrlCode = findFieldCode(
        properties,
        ['invoice_pdf_url', 'pdf_url', 'estimate_pdf_url', 'document_url'],
        ['見積書PDF URL', 'PDF URL', '帳票URL', 'ファイルURL'],
        'LINK'
      );
      const attachmentCode = (() => {
        const keys = Object.keys(properties || {});
        const preferred = keys.find((code) => {
          const prop = properties[code];
          if (!prop || prop.type !== 'FILE') {
            return false;
          }
          const label = normalizeLabel(prop.label || '');
          const normalizedCode = normalizeLabel(code);
          return label.includes(normalizeLabel('PDF'))
            || label.includes(normalizeLabel('見積'))
            || label.includes(normalizeLabel('請求'))
            || normalizedCode.includes(normalizeLabel('pdf'));
        });
        if (preferred) {
          return preferred;
        }
        return keys.find((code) => properties[code] && properties[code].type === 'FILE') || '';
      })();
      INVOICE_FIELD_CODES_CACHE = {
        appId: invoiceAppId,
        periodCode,
        periodType,
        typeCode,
        typeFieldType,
        ownerCode,
        ownerFieldType,
        clientCompanyCode,
        clientCompanyFieldType,
        subjectCode,
        invoiceIdCode,
        pdfUrlCode,
        attachmentCode,
        fixedOfficeFeeCode
      };
      return INVOICE_FIELD_CODES_CACHE;
    })).catch(() => ({
      appId: CONFIG.apps.invoices,
      periodCode: 'period_key',
      periodType: '',
      typeCode: '',
      typeFieldType: '',
      ownerCode: '',
      ownerFieldType: '',
      clientCompanyCode: '',
      clientCompanyFieldType: '',
      subjectCode: '',
      invoiceIdCode: 'invoice_id',
      pdfUrlCode: 'invoice_pdf_url',
      attachmentCode: '',
      fixedOfficeFeeCode: ''
    }));
  }

  function setRecordFieldValue(record, code, fieldType, value) {
    if (!record || !code) {
      return;
    }
    if (fieldType === 'CHECK_BOX' || fieldType === 'MULTI_SELECT') {
      const values = Array.isArray(value) ? value : (value ? [String(value)] : []);
      record[code] = { value: values };
      return;
    }
    record[code] = { value: value == null ? '' : String(value) };
  }

  function pickDropDownValue(prop, preferredValue) {
    const options = (prop && prop.options) || {};
    const keys = Object.keys(options);
    if (!keys.length) {
      return '';
    }
    if (preferredValue && keys.includes(preferredValue)) {
      return preferredValue;
    }
    return keys[0];
  }

  function resolveInvoiceDocumentTypeValue(prop, selectedType) {
    const normalized = String(selectedType || '').trim();
    const options = (prop && prop.options) || {};
    const keys = Object.keys(options);
    if (!keys.length) {
      return normalized;
    }
    if (!normalized) {
      return keys[0];
    }
    if (keys.includes(normalized)) {
      return normalized;
    }

    const mode = normalized.includes('見積') ? 'estimate' : (normalized.includes('請求') ? 'invoice' : 'other');
    const matchedByKey = keys.find((key) => {
      const text = String(key || '');
      if (mode === 'estimate') {
        return text.includes('見積');
      }
      if (mode === 'invoice') {
        return text.includes('請求');
      }
      return false;
    });
    if (matchedByKey) {
      return matchedByKey;
    }

    const matchedByLabel = keys.find((key) => {
      const label = String((options[key] && options[key].label) || '');
      if (mode === 'estimate') {
        return label.includes('見積');
      }
      if (mode === 'invoice') {
        return label.includes('請求');
      }
      return false;
    });
    if (matchedByLabel) {
      return matchedByLabel;
    }

    return keys[0];
  }

  function buildDefaultRequiredValue(fieldCode, prop, periodKey) {
    if (!prop) {
      return '';
    }
    const type = prop.type;
    if (type === 'NUMBER') {
      if (fieldCode === 'version') {
        return '1';
      }
      return '0';
    }
    if (type === 'DATE') {
      const y = String(periodKey || '').slice(0, 4);
      const m = String(periodKey || '').slice(4, 6) || '01';
      return `${y || '2026'}-${m}-01`;
    }
    if (type === 'DROP_DOWN' || type === 'RADIO_BUTTON') {
      return pickDropDownValue(prop, fieldCode === 'status' ? 'preparing' : '');
    }
    if (type === 'CHECK_BOX' || type === 'MULTI_SELECT') {
      const picked = pickDropDownValue(prop, '');
      return picked ? [picked] : [];
    }
    if (type === 'SINGLE_LINE_TEXT') {
      if (fieldCode === 'id' || fieldCode === 'invoice_id') {
        const suffix = String(Date.now()).slice(-6);
        return `INV-${periodKey || '000000'}-${suffix}`;
      }
      if (fieldCode === 'client_id') {
        return 'DUMMY_CLIENT';
      }
      return `DUMMY_${periodKey || '000000'}`;
    }
    return '';
  }

  function valueMatchesTypeField(record, typeCode, fieldType, documentType) {
    if (!typeCode || !documentType) {
      return true;
    }
    const field = record && record[typeCode] ? record[typeCode].value : null;
    if (fieldType === 'CHECK_BOX' || fieldType === 'MULTI_SELECT') {
      return Array.isArray(field) && field.includes(documentType);
    }
    return String(field || '').trim() === String(documentType || '').trim();
  }

  function valueMatchesSubjectField(record, subjectCode, subjectValue) {
    if (!subjectCode) {
      return true;
    }
    const expected = String(subjectValue || '').trim();
    if (!expected) {
      return true;
    }
    const actual = record && record[subjectCode] ? String(record[subjectCode].value || '').trim() : '';
    return actual === expected;
  }

  function getRecordIdValue(record) {
    const idValue = record && record.$id && record.$id.value ? String(record.$id.value).trim() : '';
    return idValue;
  }

  function pickLatestRecord(records) {
    const list = Array.isArray(records) ? records : [];
    if (!list.length) {
      return null;
    }
    return list.slice().sort((a, b) => {
      const av = Number(getRecordIdValue(a));
      const bv = Number(getRecordIdValue(b));
      if (!Number.isFinite(av) || !Number.isFinite(bv)) {
        return getRecordIdValue(a).localeCompare(getRecordIdValue(b), 'ja', { numeric: true });
      }
      return bv - av;
    })[0];
  }

  async function ensureInvoiceRecordExists(invoiceFields, periodKey, documentType, responsible, subject, fixedOfficeFeeAmount, hasFixedOfficeFee, options) {
    const forceCreate = !!(options && options.forceCreate);
    const clientCompany = String((options && options.clientCompany) || '').trim();
    const properties = await fetchFormFields(invoiceFields.appId);
    const resolvedDocumentType = invoiceFields.typeCode
      ? resolveInvoiceDocumentTypeValue(properties[invoiceFields.typeCode], documentType)
      : documentType;
    const baseQueryParts = [buildKintoneFieldCondition(invoiceFields.periodCode, invoiceFields.periodType, periodKey)];
    if (invoiceFields.ownerCode) {
      baseQueryParts.push(buildKintoneFieldCondition(invoiceFields.ownerCode, invoiceFields.ownerFieldType, responsible));
    }
    if (clientCompany && invoiceFields.clientCompanyCode) {
      baseQueryParts.push(buildKintoneFieldCondition(invoiceFields.clientCompanyCode, invoiceFields.clientCompanyFieldType, clientCompany));
    }
    const baseQuery = `${baseQueryParts.join(' and ')} order by $id asc limit 500`;

    const fetchFields = ['$id'];
    if (invoiceFields.typeCode) {
      fetchFields.push(invoiceFields.typeCode);
    }
    if (invoiceFields.fixedOfficeFeeCode) {
      fetchFields.push(invoiceFields.fixedOfficeFeeCode);
    }
    if (invoiceFields.subjectCode) {
      fetchFields.push(invoiceFields.subjectCode);
    }
    if (invoiceFields.clientCompanyCode) {
      fetchFields.push(invoiceFields.clientCompanyCode);
    }

    let records = await fetchRecords(invoiceFields.appId, baseQuery, fetchFields);
    let typedRecords = records.filter((record) => {
      return valueMatchesTypeField(record, invoiceFields.typeCode, invoiceFields.typeFieldType, resolvedDocumentType)
        && valueMatchesSubjectField(record, invoiceFields.subjectCode, subject);
    });
    if (forceCreate) {
      typedRecords = [];
    }
    let created = false;
    let createdRecordId = '';

    if (!typedRecords.length) {
      const newRecord = {};

      setRecordFieldValue(newRecord, invoiceFields.periodCode, invoiceFields.periodType, periodKey);
      setRecordFieldValue(newRecord, invoiceFields.ownerCode, invoiceFields.ownerFieldType, responsible);
      setRecordFieldValue(newRecord, invoiceFields.typeCode, invoiceFields.typeFieldType, resolvedDocumentType);
      if (invoiceFields.clientCompanyCode && clientCompany) {
        setRecordFieldValue(newRecord, invoiceFields.clientCompanyCode, invoiceFields.clientCompanyFieldType, clientCompany);
      }
      if (invoiceFields.subjectCode) {
        setRecordFieldValue(newRecord, invoiceFields.subjectCode, (properties[invoiceFields.subjectCode] && properties[invoiceFields.subjectCode].type) || '', subject);
      }
      if (invoiceFields.fixedOfficeFeeCode && hasFixedOfficeFee) {
        setRecordFieldValue(newRecord, invoiceFields.fixedOfficeFeeCode, (properties[invoiceFields.fixedOfficeFeeCode] && properties[invoiceFields.fixedOfficeFeeCode].type) || '', fixedOfficeFeeAmount);
      }

      Object.keys(properties || {}).forEach((code) => {
        const prop = properties[code];
        if (!prop || !prop.required || newRecord[code]) {
          return;
        }
        const skipTypes = ['RECORD_NUMBER', 'CREATOR', 'CREATED_TIME', 'MODIFIER', 'UPDATED_TIME', 'REFERENCE_TABLE', 'SUBTABLE', 'CALC', 'LABEL', 'SPACER', 'HR'];
        if (skipTypes.includes(prop.type)) {
          return;
        }
        const fallback = buildDefaultRequiredValue(code, prop, periodKey);
        if (fallback === '' || fallback == null) {
          return;
        }
        setRecordFieldValue(newRecord, code, prop.type, fallback);
      });

      const createdResp = await kintone.api(buildQueryPath('record.json'), 'POST', {
        app: invoiceFields.appId,
        record: newRecord
      });
      created = true;
      createdRecordId = createdResp && createdResp.id ? String(createdResp.id) : '';

      records = await fetchRecords(invoiceFields.appId, baseQuery, fetchFields);
      typedRecords = records.filter((record) => {
        return valueMatchesTypeField(record, invoiceFields.typeCode, invoiceFields.typeFieldType, resolvedDocumentType)
          && valueMatchesSubjectField(record, invoiceFields.subjectCode, subject);
      });
    }

    return {
      baseQuery,
      typedRecords,
      created,
      createdRecordId
    };
  }

  function resolvePayoutFieldCodes() {
    if (PAYOUT_FIELD_CODES_CACHE) {
      return Promise.resolve(PAYOUT_FIELD_CODES_CACHE);
    }
    return resolveBillingAppId('payouts').then((payoutAppId) => fetchFormFields(payoutAppId).then((properties) => {
      const periodCode = findFieldCode(
        properties,
        ['period_key'],
        ['期間', '対象月', '年月'],
        ''
      ) || 'period_key';
      const workerCode = findFieldCode(
        properties,
        ['worker_id'],
        ['稼働者ID', '稼働者'],
        ''
      ) || 'worker_id';
      const payoutIdCode = findFieldCode(
        properties,
        ['payout_id'],
        ['支払明細ID', '支払ID'],
        ''
      ) || 'payout_id';
      const supplierCode = findFieldCode(
        properties,
        ['supplier_id', 'introducer_supplier_id'],
        ['下請けID', '紹介者ID', '支払先ID', '紹介者/下請け'],
        ''
      ) || '';
      const paymentDateCode = findFieldCode(
        properties,
        ['payment_date', 'pay_date'],
        ['支払日', '振込日'],
        'DATE'
      ) || '';
      const closedAtCode = findFieldCode(
        properties,
        ['closed_at', 'close_date'],
        ['締め日', '締日'],
        'DATE'
      ) || '';
      const parentPayoutIdCode = findFieldCode(
        properties,
        ['parent_payout_id'],
        ['親支払明細ID', '親ID'],
        ''
      ) || '';
      const projectCode = findFieldCode(
        properties,
        ['project_id'],
        ['案件ID', '案件'],
        ''
      ) || '';
      const pdfUrlCode = findFieldCode(
        properties,
        ['payout_pdf_url', 'pdf_url', 'document_url'],
        ['支払明細PDF URL', 'PDF URL', '帳票URL'],
        'LINK'
      ) || '';
      const noteCode = findFieldCode(
        properties,
        ['notes', 'note', 'remarks', 'comment'],
        ['備考', 'メモ', 'コメント', '摘要備考'],
        ''
      ) || '';
      const periodType = (properties[periodCode] && properties[periodCode].type) ? properties[periodCode].type : '';
      const workerFieldType = (properties[workerCode] && properties[workerCode].type) ? properties[workerCode].type : '';
      const supplierFieldType = (supplierCode && properties[supplierCode] && properties[supplierCode].type) ? properties[supplierCode].type : '';
      const paymentDateType = (paymentDateCode && properties[paymentDateCode] && properties[paymentDateCode].type) ? properties[paymentDateCode].type : '';
      const closedAtType = (closedAtCode && properties[closedAtCode] && properties[closedAtCode].type) ? properties[closedAtCode].type : '';
      const parentPayoutIdType = (parentPayoutIdCode && properties[parentPayoutIdCode] && properties[parentPayoutIdCode].type) ? properties[parentPayoutIdCode].type : '';
      const projectFieldType = (projectCode && properties[projectCode] && properties[projectCode].type) ? properties[projectCode].type : '';

      const attachmentCode = (() => {
        const keys = Object.keys(properties || {});
        const preferred = keys.find((code) => {
          const prop = properties[code];
          if (!prop || prop.type !== 'FILE') {
            return false;
          }
          const label = normalizeLabel(prop.label || '');
          return label.includes(normalizeLabel('PDF')) || normalizeLabel(code).includes(normalizeLabel('pdf'));
        });
        if (preferred) {
          return preferred;
        }
        return keys.find((code) => properties[code] && properties[code].type === 'FILE') || '';
      })();

      PAYOUT_FIELD_CODES_CACHE = {
        appId: payoutAppId,
        periodCode,
        periodType,
        workerCode,
        workerFieldType,
        supplierCode,
        supplierFieldType,
        payoutIdCode,
        paymentDateCode,
        paymentDateType,
        closedAtCode,
        closedAtType,
        parentPayoutIdCode,
        parentPayoutIdType,
        projectCode,
        projectFieldType,
        noteCode,
        pdfUrlCode,
        attachmentCode
      };
      return PAYOUT_FIELD_CODES_CACHE;
    })).catch(() => ({
      appId: CONFIG.apps.payouts,
      periodCode: 'period_key',
      periodType: '',
      workerCode: 'worker_id',
      workerFieldType: '',
      supplierCode: 'supplier_id',
      supplierFieldType: '',
      payoutIdCode: 'payout_id',
      paymentDateCode: 'payment_date',
      paymentDateType: 'DATE',
      closedAtCode: 'closed_at',
      closedAtType: 'DATE',
      parentPayoutIdCode: 'parent_payout_id',
      parentPayoutIdType: '',
      projectCode: 'project_id',
      projectFieldType: '',
      noteCode: 'notes',
      pdfUrlCode: 'payout_pdf_url',
      attachmentCode: ''
    }));
  }

  async function ensurePayoutRecordExists(payoutFields, periodKey, workerId, options) {
    const appId = payoutFields.appId;
    const properties = await fetchFormFields(appId);
    const periodType = payoutFields.periodType || ((properties[payoutFields.periodCode] && properties[payoutFields.periodCode].type) || '');
    const workerFieldType = payoutFields.workerFieldType || ((properties[payoutFields.workerCode] && properties[payoutFields.workerCode].type) || '');
    const supplierId = options && options.supplierId ? String(options.supplierId).trim() : '';
    const supplierCode = payoutFields.supplierCode || '';
    const supplierFieldType = payoutFields.supplierFieldType || ((supplierCode && properties[supplierCode] && properties[supplierCode].type) || '');
    const effectiveWorkerId = String(workerId || '').trim();

    const whereParts = [buildKintoneFieldCondition(payoutFields.periodCode, periodType, periodKey)];
    if (supplierId && supplierCode) {
      whereParts.push(buildKintoneFieldCondition(supplierCode, supplierFieldType, supplierId));
    } else {
      whereParts.push(buildKintoneFieldCondition(payoutFields.workerCode, workerFieldType, effectiveWorkerId));
    }
    const queryIdentity = supplierId && supplierCode ? supplierId : effectiveWorkerId;

    const baseQuery = `${whereParts.join(' and ')} order by $id asc limit 500`;
    const fetchFields = ['$id', payoutFields.periodCode, payoutFields.workerCode, supplierCode, payoutFields.payoutIdCode].filter(Boolean);
    let records = await fetchRecords(appId, baseQuery, fetchFields);
    let created = false;
    let createdRecordId = '';

    if (!records.length) {
      const newRecord = {};
      setRecordFieldValue(newRecord, payoutFields.periodCode, periodType, periodKey);
      if (!(supplierId && supplierCode)) {
        setRecordFieldValue(newRecord, payoutFields.workerCode, workerFieldType, effectiveWorkerId);
      }
      if (supplierId && supplierCode) {
        setRecordFieldValue(newRecord, supplierCode, supplierFieldType, supplierId);
      }
      if (payoutFields.payoutIdCode) {
        const payoutIdType = (properties[payoutFields.payoutIdCode] && properties[payoutFields.payoutIdCode].type) || '';
        setRecordFieldValue(newRecord, payoutFields.payoutIdCode, payoutIdType, `PD-${periodKey}-${queryIdentity}`);
      }
      if (payoutFields.paymentDateCode) {
        setRecordFieldValue(newRecord, payoutFields.paymentDateCode, payoutFields.paymentDateType || 'DATE', computePayoutPaymentDate(periodKey));
      }
      if (payoutFields.closedAtCode) {
        setRecordFieldValue(newRecord, payoutFields.closedAtCode, payoutFields.closedAtType || 'DATE', computePayoutCloseDate(periodKey));
      }

      Object.keys(properties || {}).forEach((code) => {
        const prop = properties[code];
        if (!prop || !prop.required || newRecord[code]) {
          return;
        }
        const skipTypes = ['RECORD_NUMBER', 'CREATOR', 'CREATED_TIME', 'MODIFIER', 'UPDATED_TIME', 'REFERENCE_TABLE', 'SUBTABLE', 'CALC', 'LABEL', 'SPACER', 'HR'];
        if (skipTypes.includes(prop.type)) {
          return;
        }
        const fallback = buildDefaultRequiredValue(code, prop, periodKey);
        if (fallback === '' || fallback == null) {
          return;
        }
        setRecordFieldValue(newRecord, code, prop.type, fallback);
      });

      const createdResp = await kintone.api(buildQueryPath('record.json'), 'POST', {
        app: appId,
        record: newRecord
      });
      created = true;
      createdRecordId = createdResp && createdResp.id ? String(createdResp.id) : '';

      records = await fetchRecords(appId, baseQuery, fetchFields);
    }

    const latest = pickLatestRecord(records);
    return {
      created,
      recordId: createdRecordId || getRecordIdValue(latest),
      query: `${whereParts.join(' and ')} order by $id desc`,
      targetWorkerId: effectiveWorkerId,
      targetSupplierId: supplierId
    };
  }

  function resolveWorkerFieldCodes() {
    if (WORKER_FIELD_CODES_CACHE) {
      return Promise.resolve(WORKER_FIELD_CODES_CACHE);
    }
    return fetchFormFields(CONFIG.apps.workers).then((properties) => {
      const viaCode = findFieldCode(
        properties,
        ['via_destination', 'group'],
        ['経由先', '所属区分', '紹介区分'],
        ''
      ) || 'via_destination';
      const introducerCode = findFieldCode(
        properties,
        ['introducer_supplier', 'introducer_supplier_id'],
        ['紹介者', '下請け', '紹介元'],
        ''
      ) || 'introducer_supplier';
      const lastNameCode = findFieldCode(
        properties,
        ['last_name', 'lastname', 'sei'],
        ['氏名(姓)', '姓'],
        ''
      ) || 'last_name';
      const firstNameCode = findFieldCode(
        properties,
        ['first_name', 'firstname', 'mei'],
        ['氏名(名)', '名'],
        ''
      ) || 'first_name';
      const fullNameCode = findFieldCode(
        properties,
        ['name', 'worker_name', 'full_name'],
        ['氏名', '名前', 'フルネーム'],
        ''
      ) || 'name';

      const idTypeAllow = new Set(['SINGLE_LINE_TEXT', 'DROP_DOWN', 'RADIO_BUTTON', 'NUMBER']);
      const idCandidateCodes = Object.keys(properties || {}).filter((code) => {
        const prop = properties[code] || {};
        const label = String(prop.label || '');
        const lowerCode = String(code || '').toLowerCase();
        if (!idTypeAllow.has(String(prop.type || ''))) {
          return false;
        }
        if (lowerCode === 'worker_id' || lowerCode === 'id') {
          return true;
        }
        if (lowerCode.includes('id') || lowerCode.includes('uuid') || lowerCode.includes('ulid') || lowerCode.includes('key')) {
          return true;
        }
        return label.includes('ID') || label.includes('識別') || label.includes('キー');
      });

      WORKER_FIELD_CODES_CACHE = {
        viaCode,
        introducerCode,
        lastNameCode,
        firstNameCode,
        fullNameCode,
        idCandidateCodes: Array.from(new Set(['worker_id'].concat(idCandidateCodes)))
      };
      return WORKER_FIELD_CODES_CACHE;
    }).catch(() => ({
      viaCode: 'via_destination',
      introducerCode: 'introducer_supplier',
      lastNameCode: 'last_name',
      firstNameCode: 'first_name',
      fullNameCode: 'name',
      idCandidateCodes: ['worker_id', 'id', 'worker_ulid', 'worker_uuid', 'worker_key']
    }));
  }

  function ensureJsZipLoaded() {
    if (window.JSZip) {
      return Promise.resolve(window.JSZip);
    }
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-vanzai-jszip="1"]');
      if (existing) {
        existing.addEventListener('load', () => resolve(window.JSZip));
        existing.addEventListener('error', () => reject(new Error('JSZipの読み込みに失敗しました')));
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
      script.async = true;
      script.dataset.vanzaiJszip = '1';
      script.onload = () => resolve(window.JSZip);
      script.onerror = () => reject(new Error('JSZipの読み込みに失敗しました'));
      document.head.appendChild(script);
    });
  }

  function fetchFileBlobByKey(fileKey) {
    const key = String(fileKey || '').trim();
    if (!key) {
      return Promise.reject(new Error('PDF取得失敗: fileKeyが空です'));
    }

    const endpoints = [];
    const pushUnique = (url) => {
      const value = String(url || '').trim();
      if (!value) {
        return;
      }
      if (!endpoints.includes(value)) {
        endpoints.push(value);
      }
    };

    pushUnique(buildQueryPath('file.json'));
    pushUnique('/k/v1/file.json');

    const tryFetch = (index) => {
      if (index >= endpoints.length) {
        throw new Error('PDF取得失敗: HTTP 400（fileKeyの有効性または権限を確認してください）');
      }
      const url = `${endpoints[index]}?fileKey=${encodeURIComponent(key)}`;
      return fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      }).then((res) => {
        if (res.ok) {
          return res.blob();
        }
        if ((res.status === 400 || res.status === 404) && index < endpoints.length - 1) {
          return tryFetch(index + 1);
        }
        throw new Error(`PDF取得失敗: HTTP ${res.status}`);
      });
    };

    return tryFetch(0);
  }

  function ensureJsPdfLoaded() {
    if (window.jspdf && window.jspdf.jsPDF) {
      return Promise.resolve(window.jspdf.jsPDF);
    }
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-vanzai-jspdf="1"]');
      if (existing) {
        existing.addEventListener('load', () => {
          if (window.jspdf && window.jspdf.jsPDF) {
            resolve(window.jspdf.jsPDF);
            return;
          }
          reject(new Error('jsPDFの読み込みに失敗しました'));
        });
        existing.addEventListener('error', () => reject(new Error('jsPDFの読み込みに失敗しました')));
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
      script.async = true;
      script.dataset.vanzaiJspdf = '1';
      script.onload = () => {
        if (window.jspdf && window.jspdf.jsPDF) {
          resolve(window.jspdf.jsPDF);
          return;
        }
        reject(new Error('jsPDFの読み込みに失敗しました'));
      };
      script.onerror = () => reject(new Error('jsPDFの読み込みに失敗しました'));
      document.head.appendChild(script);
    });
  }

  function buildInvoicePdfBlob(payload) {
    return ensureJsPdfLoaded().then((jsPDF) => {
      const canvas = document.createElement('canvas');
      canvas.width = 1240;
      canvas.height = 1754;
      const context = canvas.getContext('2d');
      if (!context) {
        throw new Error('PDF描画の初期化に失敗しました');
      }

      const SCALE = 0.92;
      const OFFSET_X = 22;
      const OFFSET_Y = 18;

      const drawCell = (x, y, w, h, text, align, font, fill, borderStyle) => {
        if (fill) {
          context.fillStyle = fill;
          context.fillRect(x, y, w, h);
        }
        if (borderStyle !== 'none') {
          context.strokeStyle = borderStyle === 'bold' ? '#1f2937' : '#e5e7eb';
          context.lineWidth = borderStyle === 'bold' ? 2 : 1;
          context.strokeRect(x, y, w, h);
        }
        context.fillStyle = '#111827';
        context.font = font || '500 24px sans-serif';
        context.textAlign = align || 'left';
        const pad = 10;
        const tx = align === 'right' ? x + w - pad : (align === 'center' ? x + (w / 2) : x + pad);
        const ty = y + (h / 2) + 8;
        context.fillText(String(text || ''), tx, ty);
      };
      const amountNum = (value) => {
        const num = Number(
          String(value == null ? '' : value)
            .replace(/[¥￥,，\s]/g, '')
            .trim()
        );
        return Number.isFinite(num) ? num : 0;
      };
      const fmt = (num) => Number(num || 0).toLocaleString('ja-JP');
      const lineItems = Array.isArray(payload.lineItems) ? payload.lineItems : [];
      const registrationNo = String(payload.registrationNumber || 'T2011201021906').trim();
      const addressee = String(payload.addressee || payload.responsible || '-').trim();
      const nonTaxAmountNum = amountNum(payload.nonTaxAmount);
      const docTitle = String(payload.documentType || '').includes('請求') ? '御　請　求　書' : '御　見　積　書';

      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.save();
      context.translate(OFFSET_X, OFFSET_Y);
      context.scale(SCALE, SCALE);

      context.fillStyle = '#0b1220';
      context.font = '700 58px sans-serif';
      context.textAlign = 'center';
      context.fillText(docTitle, canvas.width / 2, 118);
      context.strokeStyle = '#14b8a6';
      context.lineWidth = 4;
      context.beginPath();
      context.moveTo(56, 136);
      context.lineTo(1184, 136);
      context.stroke();

      context.textAlign = 'left';
      context.font = '600 32px sans-serif';
      context.fillStyle = '#0f172a';
      context.fillText(addressee || '-', 86, 258);

      context.strokeStyle = '#1f2937';
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(56, 280);
      context.lineTo(560, 280);
      context.stroke();

      context.textAlign = 'right';
      context.font = '600 25px sans-serif';
      context.fillStyle = '#0f172a';
      context.fillText('御見積日', 890, 220);
      context.fillText(new Date().toLocaleDateString('ja-JP').replace(/\//g, '/'), 1184, 220);
      context.fillText('登録番号', 890, 280);
      context.font = '600 23px sans-serif';
      context.fillText(registrationNo, 1184, 280);

      context.textAlign = 'left';
      context.font = '600 32px sans-serif';
      context.fillStyle = '#111827';
      context.fillText('株式会社VANZAI', 640, 350);
      context.font = '500 24px sans-serif';
      context.fillText('〒116-0002', 640, 396);
      context.fillText('東京都荒川区荒川1丁目39-1', 640, 438);
      context.fillText('東京アルバタワー1703', 640, 480);
      context.fillText('TEL : 03-6822-0970', 640, 522);
      context.fillText('E-Mail : vanzai.official@gmail.com', 640, 564);

      context.strokeStyle = '#ef4444';
      context.lineWidth = 4;
      context.beginPath();
      context.arc(1000, 455, 90, 0, Math.PI * 2);
      context.stroke();
      context.textAlign = 'center';
      context.fillStyle = '#ef4444';
      context.font = '700 36px sans-serif';
      context.fillText('株式会社', 1000, 424);
      context.fillText('VANZAI', 1000, 472);
      context.fillText('会社印', 1000, 520);

      context.textAlign = 'left';
      context.font = '500 22px sans-serif';
      context.fillStyle = '#111827';
      context.fillText('下記の通り御見積申し上げます。', 56, 640);

      context.textAlign = 'left';
      context.font = '600 30px sans-serif';
      context.fillStyle = '#111827';
      const subjectLabel = '件　名：';
      const subjectText = String(payload.subject || '-');
      const subjectMaxWidth = 1100;
      const subjectFirstLineMax = Math.max(subjectMaxWidth - context.measureText(subjectLabel).width, 120);
      const subjectMaxLines = 2;
      const subjectLines = [];
      let currentLine = '';
      for (let i = 0; i < subjectText.length; i += 1) {
        const testLine = currentLine + subjectText[i];
        const limit = subjectLines.length === 0 ? subjectFirstLineMax : subjectMaxWidth;
        const measured = context.measureText(testLine).width;
        if (measured > limit && currentLine) {
          subjectLines.push(currentLine);
          currentLine = subjectText[i];
        } else {
          currentLine = testLine;
        }
      }
      if (currentLine) {
        subjectLines.push(currentLine);
      }
      if (!subjectLines.length) {
        subjectLines.push('-');
      }
      if (subjectLines.length > subjectMaxLines) {
        const mergedLast = `${subjectLines[subjectMaxLines - 1]}…`;
        subjectLines.splice(subjectMaxLines - 1, subjectLines.length - (subjectMaxLines - 1), mergedLast);
      }
      subjectLines.forEach((line, index) => {
        const y = 708 + (index * 40);
        if (index === 0) {
          context.fillText(`${subjectLabel}${line}`, 56, y);
        } else {
          context.fillText(`　　　　${line}`, 56, y);
        }
      });
      const subjectHeight = subjectLines.length * 40;

      let subtotalNum = amountNum(payload.subtotal);
      const fixedOfficeFeeNum = amountNum(payload.fixedOfficeFee);
      let taxNum = amountNum(payload.taxAmount);
      let totalNum = amountNum(payload.totalAmount);
      if (subtotalNum <= 0 && fixedOfficeFeeNum > 0) {
        subtotalNum = fixedOfficeFeeNum;
      }
      if (taxNum <= 0 && subtotalNum > 0) {
        taxNum = Math.floor(subtotalNum * 0.1);
      }
      if (totalNum <= 0 && subtotalNum > 0) {
        totalNum = subtotalNum + taxNum;
      }

      const amountBlockY = 708 + subjectHeight + 20;
      context.fillStyle = '#eef2ff';
      context.fillRect(610, amountBlockY - 44, 574, 62);
      context.textAlign = 'left';
      context.fillStyle = '#0f172a';
      context.font = '700 42px sans-serif';
      context.fillText('ご請求金額', 620, amountBlockY);
      context.textAlign = 'right';
      context.font = '700 50px sans-serif';
      context.fillText(`¥${fmt(totalNum)}`, 1184, amountBlockY);
      context.strokeStyle = '#0f172a';
      context.lineWidth = 3;
      context.beginPath();
      context.moveTo(620, amountBlockY + 18);
      context.lineTo(1184, amountBlockY + 18);
      context.stroke();

      const tableX = 56;
      const tableY = amountBlockY + 36;
      const colW = [410, 100, 250, 368];
      const rowH = 52;
      const tableTotalW = colW.reduce((sum, width) => sum + width, 0);
      const headers = ['商品名', '数量', '単価', '金額'];
      const maxRows = 12;
      const nonTaxRows = 1;
      const totalRows = 1 + maxRows + 1 + nonTaxRows;

      context.fillStyle = '#111827';
      context.fillRect(tableX, tableY, tableTotalW, rowH);
      let colStart = tableX;
      headers.forEach((header, index) => {
        context.fillStyle = '#f8fafc';
        context.font = '700 26px sans-serif';
        context.textAlign = 'center';
        context.fillText(header, colStart + (colW[index] / 2), tableY + (rowH / 2) + 10);
        colStart += colW[index];
      });
      context.strokeStyle = '#374151';
      context.lineWidth = 1.5;
      context.beginPath();
      context.moveTo(tableX, tableY + rowH);
      context.lineTo(tableX + tableTotalW, tableY + rowH);
      context.stroke();

      const nonOfficeSubtotalNum = Math.max(subtotalNum - fixedOfficeFeeNum, 0);
      const sourceLineItems = lineItems.length ? lineItems.slice() : [
        { name: '稼働人工', quantity: '一式', unitPrice: nonOfficeSubtotalNum, amount: nonOfficeSubtotalNum },
        { name: '固定事務局費', quantity: '一式', unitPrice: fixedOfficeFeeNum, amount: fixedOfficeFeeNum }
      ];
      const hasOfficeFeeRow = sourceLineItems.some((item) => {
        const name = String(item && item.name || '');
        return name.includes('運営協力費') || name.includes('固定事務局費');
      });
      if (!hasOfficeFeeRow && fixedOfficeFeeNum > 0) {
        sourceLineItems.push({ name: '固定事務局費', quantity: '一式', unitPrice: fixedOfficeFeeNum, amount: fixedOfficeFeeNum });
      }
      const rows = sourceLineItems.map((item) => {
        const originalName = String(item.name || '').trim();
        const name = originalName.includes('運営協力費') ? originalName.replace('運営協力費', '固定事務局費') : originalName;
        return [
          name,
          name ? (item.quantity || '一式') : '',
          name ? `¥${fmt(item.unitPrice || 0)}` : '',
          name ? `¥${fmt(item.amount || 0)}` : ''
        ];
      });

      const displayRows = rows.slice(0, maxRows);
      while (displayRows.length < maxRows) {
        displayRows.push(['', '', '', '']);
      }

      displayRows.forEach((row, rowIndex) => {
        const yMid = tableY + rowH * (rowIndex + 1) + (rowH / 2) + 8;
        if (row[0] && rowIndex % 2 === 0) {
          context.fillStyle = '#f8fafc';
          context.fillRect(tableX, tableY + rowH * (rowIndex + 1), tableTotalW, rowH);
        }
        let rowX = tableX;
        context.fillStyle = '#111827';
        context.font = '500 22px sans-serif';
        context.textAlign = 'left';
        if (row[0]) {
          context.fillText(row[0], rowX + 10, yMid);
        }
        rowX += colW[0];

        context.textAlign = 'center';
        if (row[1]) {
          context.fillText(row[1], rowX + (colW[1] / 2), yMid);
        }
        rowX += colW[1];

        context.textAlign = 'right';
        if (row[2]) {
          context.fillText(row[2], rowX + colW[2] - 10, yMid);
        }
        rowX += colW[2];
        if (row[3]) {
          context.fillText(row[3], rowX + colW[3] - 10, yMid);
        }

        if (rowIndex < maxRows - 1) {
          context.strokeStyle = '#e5e7eb';
          context.lineWidth = 1;
          context.beginPath();
          context.moveTo(tableX, tableY + rowH * (rowIndex + 2));
          context.lineTo(tableX + tableTotalW, tableY + rowH * (rowIndex + 2));
          context.stroke();
        }
      });
      context.strokeStyle = '#9ca3af';
      context.lineWidth = 1.5;
      context.strokeRect(tableX, tableY, tableTotalW, rowH * (maxRows + 1));

      const sectionIndex = 1 + maxRows;
      const sectionYMid = tableY + rowH * sectionIndex + (rowH / 2) + 8;
      context.textAlign = 'left';
      context.fillStyle = '#6b7280';
      context.font = '600 23px sans-serif';
      context.fillText('▼ 非課税処理', tableX + 10, sectionYMid);

      for (let i = 0; i < nonTaxRows; i += 1) {
        const lineY = tableY + rowH * (sectionIndex + 2 + i);
        context.strokeStyle = '#f3f4f6';
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(tableX, lineY);
        context.lineTo(tableX + tableTotalW, lineY);
        context.stroke();
      }
      context.strokeStyle = '#1f2937';
      context.lineWidth = 2;
      context.strokeRect(tableX, tableY + rowH * sectionIndex, tableTotalW, rowH * (nonTaxRows + 1));

      const summaryTop = tableY + rowH * totalRows + 18;
      drawCell(588, summaryTop, 228, 52, '小　計', 'center', '600 24px sans-serif', '#ffffff', 'bold');
      drawCell(816, summaryTop, 368, 52, `¥${fmt(subtotalNum)}`, 'right', '600 24px sans-serif', '#ffffff', 'bold');
      drawCell(588, summaryTop + 52, 228, 52, '消 費 税 (10%)', 'center', '600 24px sans-serif', '#ffffff', 'bold');
      drawCell(816, summaryTop + 52, 368, 52, `¥${fmt(taxNum)}`, 'right', '600 24px sans-serif', '#ffffff', 'bold');
      drawCell(588, summaryTop + 104, 228, 52, '非 課 税 額', 'center', '600 24px sans-serif', '#ffffff', 'bold');
      drawCell(816, summaryTop + 104, 368, 52, nonTaxAmountNum > 0 ? `¥${fmt(nonTaxAmountNum)}` : '¥ -', 'right', '600 24px sans-serif', '#ffffff', 'bold');
      drawCell(588, summaryTop + 156, 228, 52, '合　計', 'center', '700 26px sans-serif', '#f8fafc', 'bold');
      drawCell(816, summaryTop + 156, 368, 52, `¥${fmt(totalNum + nonTaxAmountNum)}`, 'right', '700 26px sans-serif', '#f8fafc', 'bold');

      context.textAlign = 'left';
      context.fillStyle = '#4b5563';
      context.font = '500 18px sans-serif';
      context.fillText(`対象月: ${payload.periodKey || '-'} / 帳票ID: ${payload.invoiceId || '-'} / レコードID: ${payload.recordId || '-'}`, 56, summaryTop + 42);
      context.fillText('※ 本PDFはシステムから自動生成されています。', 56, summaryTop + 74);
      context.restore();

      const imageData = canvas.toDataURL('image/jpeg', 0.62);
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4', compress: true });
      pdf.addImage(imageData, 'JPEG', 10, 10, 190, 277, undefined, 'MEDIUM');

      const summaryRows = Array.isArray(payload.summaryRows) ? payload.summaryRows : [];
      if (summaryRows.length) {
        pdf.addPage();
        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(16);
        pdf.text('稼働者別サマリー', 14, 18);
        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(10);
        pdf.text(`対象: ${payload.workerName || payload.workerId || '-'} / ${periodLabel}`, 14, 24);

        let y = 32;
        pdf.setFont('helvetica', 'bold');
        pdf.text('No', 14, y);
        pdf.text('稼働者', 26, y);
        pdf.text('数量', 138, y, { align: 'right' });
        pdf.text('金額', 196, y, { align: 'right' });
        pdf.setLineWidth(0.3);
        pdf.line(14, y + 2, 196, y + 2);
        y += 8;

        pdf.setFont('helvetica', 'normal');
        let total = 0;
        summaryRows.forEach((row, index) => {
          if (y > 282) {
            pdf.addPage();
            y = 20;
          }
          const qty = row && row.quantity != null ? String(row.quantity) : '-';
          const amount = parseAmountNumber(row && row.amount);
          total += amount;
          pdf.text(String(index + 1), 14, y);
          pdf.text(String((row && row.workerName) || (row && row.workerId) || '-').slice(0, 36), 26, y);
          pdf.text(qty, 138, y, { align: 'right' });
          pdf.text(`¥${fmt(amount)}`, 196, y, { align: 'right' });
          y += 6;
        });

        y += 4;
        pdf.setLineWidth(0.3);
        pdf.line(120, y, 196, y);
        y += 6;
        pdf.setFont('helvetica', 'bold');
        pdf.text('合計', 150, y, { align: 'right' });
        pdf.text(`¥${fmt(total)}`, 196, y, { align: 'right' });
      }

      return pdf.output('blob');
    });
  }

  function buildPayoutPdfBlob(payload) {
    return ensureJsPdfLoaded().then((jsPDF) => {
      const canvas = document.createElement('canvas');
      canvas.width = 1240;
      canvas.height = 1754;
      const context = canvas.getContext('2d');
      if (!context) {
        throw new Error('PDF描画の初期化に失敗しました');
      }

      const fmt = (num) => Number(num || 0).toLocaleString('ja-JP');
      const registrationNo = String(payload.registrationNumber || 'T2011201021906').trim();
      const workerName = String(payload.workerName || payload.workerId || '-').trim();
      const periodKey = String(payload.periodKey || '-');
      const parsedPeriod = parsePeriodKey(periodKey);
      const periodLabel = parsedPeriod ? `${parsedPeriod.year}年${parsedPeriod.month}月` : periodKey;
      const payoutId = String(payload.payoutId || '-');
      const paymentDate = String(payload.paymentDate || '').trim();
      const noteText = String(payload.note || '').trim();
      const lineItems = Array.isArray(payload.lineItems) ? payload.lineItems : [];
      const baseTotal = parseAmountNumber(payload.totalAmount || 0);

      const wrapTextByWidth = (text, maxWidth) => {
        const source = String(text || '');
        if (!source) {
          return [''];
        }
        const lines = [];
        let current = '';
        for (let index = 0; index < source.length; index += 1) {
          const next = current + source[index];
          if (context.measureText(next).width > maxWidth && current) {
            lines.push(current);
            current = source[index];
          } else {
            current = next;
          }
        }
        if (current) {
          lines.push(current);
        }
        return lines.length ? lines : [''];
      };

      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, canvas.width, canvas.height);

      context.fillStyle = '#111827';
      context.font = '700 44px sans-serif';
      context.textAlign = 'center';
      context.fillText('支払通知書', canvas.width / 2, 70);

      context.strokeStyle = '#c7d2fe';
      context.lineWidth = 4;
      context.beginPath();
      context.moveTo(96, 116);
      context.lineTo(1144, 116);
      context.stroke();

      context.textAlign = 'right';
      context.font = '500 22px sans-serif';
      context.fillText(`発行日：${new Date().toLocaleDateString('ja-JP')}`, 1160, 98);

      context.textAlign = 'left';
      context.font = '600 34px sans-serif';
      context.fillText(`${workerName}　様`, 96, 190);
      context.font = '500 22px sans-serif';
      context.fillText('登録番号：無し', 96, 228);
      context.strokeStyle = '#111827';
      context.lineWidth = 1.4;
      context.beginPath();
      context.moveTo(96, 206);
      context.lineTo(520, 206);
      context.stroke();
      context.beginPath();
      context.moveTo(96, 240);
      context.lineTo(520, 240);
      context.stroke();

      context.font = '500 22px sans-serif';
      context.fillText('下記の通りお支払い致します。', 96, 298);

      context.font = '600 24px sans-serif';
      context.fillText(`件名：${periodLabel}分 支払明細`, 96, 342);
      context.font = '400 20px sans-serif';
      const payoutIdLines = wrapTextByWidth(`支払明細ID：${payoutId}`, 560).slice(0, 2);
      payoutIdLines.forEach((line, idx) => {
        context.fillText(line, 96, 374 + (idx * 28));
      });
      const paymentDateLabel = paymentDate || computePayoutPaymentDate(periodKey) || '-';
      context.fillText(`支払日：${paymentDateLabel}`, 96, 374 + (payoutIdLines.length * 28) + 56);

      context.textAlign = 'left';
      context.font = '600 34px sans-serif';
      context.fillText('株式会社VANZAI', 690, 346);
      context.font = '500 24px sans-serif';
      context.fillText('〒116-0002', 690, 384);
      context.fillText('東京都荒川区荒川1丁目39-11', 690, 420);
      context.fillText('東京アルバタワー1703', 690, 456);
      context.fillText('TEL：03-6822-0970', 690, 492);
      context.fillText('E-Mail：vanzai.official@gmail.com', 690, 528);
      context.font = '400 24px sans-serif';
      context.fillText(`登録番号：${registrationNo}`, 690, 564);

      context.strokeStyle = '#ef4444';
      context.lineWidth = 4;
      context.beginPath();
      context.arc(1010, 428, 76, 0, Math.PI * 2);
      context.stroke();
      context.fillStyle = '#ef4444';
      context.font = '700 34px sans-serif';
      context.textAlign = 'center';
      context.fillText('株式会社', 1010, 392);
      context.fillText('VANZAI', 1010, 434);
      context.fillText('会社印', 1010, 476);

      context.fillStyle = '#111827';
      context.textAlign = 'left';
      context.font = '600 36px sans-serif';
      context.fillText('合計金額', 96, 592);
      const normalizedLineItems = (() => {
        const mapped = lineItems.slice();
        const sum = mapped.reduce((value, item) => value + parseAmountNumber(item && item.amount), 0);
        if (sum <= 0 && baseTotal > 0) {
          return [{
            name: '支払額調整',
            quantity: 1,
            unitPrice: baseTotal,
            amount: baseTotal
          }];
        }
        return mapped;
      })();

      const subtotalNum = normalizedLineItems.reduce((sum, item) => sum + parseAmountNumber(item && item.amount), 0);
      const taxNum = 0;
      const nonTaxNum = 0;
      const manualWithholding = parseAmountNumber(payload.withholdingTax || 0);
      const withholdingTaxNum = Math.max(
        manualWithholding > 0 ? manualWithholding : Math.floor(subtotalNum * 0.1021),
        0
      );
      const totalNum = Math.max(subtotalNum - withholdingTaxNum, 0);

      context.textAlign = 'right';
      context.font = '700 44px sans-serif';
      context.fillText(`¥${fmt(totalNum)}`, 560, 592);
      context.textAlign = 'left';
      context.font = '500 22px sans-serif';
      context.fillText('（税込）', 572, 592);
      context.strokeStyle = '#111827';
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(96, 604);
      context.lineTo(662, 604);
      context.stroke();

      const tableX = 96;
      const tableY = 630;
      const colW = [56, 444, 108, 164, 164];
      const rowH = 40;
      const maxRows = 15;
      const nonTaxRows = 3;
      const tableW = colW.reduce((sum, w) => sum + w, 0);

      const headers = ['No.', '摘要', '数量', '単価', '金額'];
      context.fillStyle = '#fff200';
      context.fillRect(tableX, tableY, tableW, rowH);

      let x = tableX;
      headers.forEach((header, idx) => {
        context.strokeStyle = '#111827';
        context.lineWidth = 1;
        context.strokeRect(x, tableY, colW[idx], rowH);
        context.fillStyle = '#111827';
        context.font = '700 22px sans-serif';
        context.textAlign = 'center';
        context.fillText(header, x + colW[idx] / 2, tableY + 27);
        x += colW[idx];
      });

      const rows = normalizedLineItems.slice(0, maxRows).map((item, idx) => {
        const rawQty = item.quantity == null ? 1 : item.quantity;
        const qtyAsNum = Number(rawQty);
        const qty = (typeof rawQty === 'string' && rawQty.trim())
          ? rawQty.trim()
          : (Number.isFinite(qtyAsNum) ? qtyAsNum : 1);
        const unitPrice = parseAmountNumber(item.unitPrice || 0);
        const amount = parseAmountNumber(item.amount || 0);
        return {
          no: idx + 1,
          name: String(item.name || '-').slice(0, 30),
          qty,
          unitPrice,
          amount
        };
      });

      while (rows.length < maxRows) {
        rows.push({ no: rows.length + 1, name: '', qty: '', unitPrice: '', amount: '' });
      }

      rows.forEach((row, idx) => {
        const y = tableY + rowH * (idx + 1);
        let cx = tableX;
        const cells = [
          row.no,
          row.name,
          row.qty === '' ? '' : row.qty,
          row.unitPrice === '' ? '' : `¥${fmt(row.unitPrice)}`,
          row.amount === '' ? '' : `¥${fmt(row.amount)}`
        ];
        for (let i = 0; i < colW.length; i += 1) {
          context.strokeStyle = '#111827';
          context.lineWidth = 1;
          context.strokeRect(cx, y, colW[i], rowH);
          context.fillStyle = '#111827';
          context.font = '500 20px sans-serif';
          context.textAlign = i <= 1 ? 'left' : 'right';
          const tx = i <= 1 ? cx + 8 : cx + colW[i] - 8;
          context.fillText(String(cells[i] || ''), tx, y + 27);
          cx += colW[i];
        }
      });

      const nonTaxTitleY = tableY + rowH * (maxRows + 1);
      context.fillStyle = '#e5e7eb';
      context.fillRect(tableX, nonTaxTitleY, tableW, rowH);
      context.strokeStyle = '#111827';
      context.strokeRect(tableX, nonTaxTitleY, tableW, rowH);
      context.fillStyle = '#111827';
      context.font = '700 22px sans-serif';
      context.textAlign = 'left';
      context.fillText('▼ 非課税処理', tableX + 8, nonTaxTitleY + 27);

      for (let i = 0; i < nonTaxRows; i += 1) {
        const y = nonTaxTitleY + rowH * (i + 1);
        context.fillStyle = '#f3f4f6';
        context.fillRect(tableX, y, tableW, rowH);
        context.strokeStyle = '#111827';
        context.lineWidth = 1;
        context.strokeRect(tableX, y, tableW, rowH);
      }

      const summaryTop = nonTaxTitleY + rowH * (nonTaxRows + 1) + 8;
      const summaryW = 352;
      const labelW = 120;
      const valueW = summaryW - labelW;
      const labelX = tableX + tableW - summaryW;
      const sRowH = 38;
      const sumRows = [
        ['小計', `¥${fmt(subtotalNum)}`, '#fff200', '#111827'],
        ['消費税(10%)', `¥${fmt(taxNum)}`, '#fff200', '#111827'],
        ['非課税額', `¥${fmt(nonTaxNum)}`, '#fff200', '#111827'],
        ['源泉所得税', `-¥${fmt(withholdingTaxNum)}`, '#fff200', '#dc2626'],
        ['合計', `¥${fmt(totalNum)}`, '#fff200', '#111827']
      ];

      sumRows.forEach((row, idx) => {
        const y = summaryTop + sRowH * idx;
        context.fillStyle = row[2];
        context.fillRect(labelX, y, labelW, sRowH);
        context.strokeStyle = '#111827';
        context.lineWidth = 1;
        context.strokeRect(labelX, y, labelW, sRowH);
        context.strokeRect(labelX + labelW, y, valueW, sRowH);

        context.fillStyle = '#111827';
        context.font = '700 20px sans-serif';
        context.textAlign = 'center';
        context.fillText(row[0], labelX + labelW / 2, y + 25);

        context.fillStyle = row[3];
        context.textAlign = 'right';
        context.fillText(row[1], labelX + labelW + valueW - 8, y + 25);
      });

      const noteY = summaryTop + sRowH * sumRows.length + 20;
      const noteHeight = Math.max(72, Math.min(140, canvas.height - noteY - 24));
      context.fillStyle = '#fff200';
      context.fillRect(tableX, noteY, 110, noteHeight);
      context.strokeStyle = '#111827';
      context.lineWidth = 1;
      context.strokeRect(tableX, noteY, tableW, noteHeight);
      context.fillStyle = '#111827';
      context.font = '700 22px sans-serif';
      context.textAlign = 'left';
      context.fillText('備考', tableX + 16, noteY + 40);
      context.fillStyle = '#1f2937';
      context.font = '500 18px sans-serif';
      const noteLines = wrapTextByWidth(noteText || '特記事項なし', tableW - 130);
      const maxNoteLines = Math.max(1, Math.floor((noteHeight - 18) / 24));
      noteLines.slice(0, maxNoteLines).forEach((line, index) => {
        context.fillText(line, tableX + 124, noteY + 28 + (index * 24));
      });

      const imageData = canvas.toDataURL('image/jpeg', 0.62);
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4', compress: true });
      pdf.addImage(imageData, 'JPEG', 10, 10, 190, 277, undefined, 'MEDIUM');
      return pdf.output('blob');
    });
  }

  function calcActualHours(record) {
    const directHours = Number(String(getFieldValue(record, 'hours') || '').trim());
    if (Number.isFinite(directHours) && directHours > 0) {
      return directHours;
    }
    const startMinutes = parseTimeValue(getFieldValue(record, 'start_time'));
    const endMinutes = parseTimeValue(getFieldValue(record, 'end_time'));
    if (startMinutes == null || endMinutes == null) {
      return 0;
    }
    let diff = endMinutes - startMinutes;
    if (diff < 0) {
      diff += 24 * 60;
    }
    const breakMinutes = Number(String(getFieldValue(record, 'break_minutes') || '0').trim());
    const netMinutes = Math.max(diff - (Number.isFinite(breakMinutes) ? breakMinutes : 0), 0);
    return netMinutes / 60;
  }

  async function buildIntroducerPayoutDetail(periodKey, introducerKey, introducerName) {
    const parsed = parsePeriodKey(periodKey);
    if (!parsed || !introducerKey) {
      return { lineItems: [], summaryRows: [] };
    }
    const workers = await fetchAllWorkers();
    const targetLabel = String(introducerName || '').trim();
    const targetKey = String(introducerKey || '').trim();

    const introducedWorkers = (workers || []).filter((record) => {
      const via = normalizeViaDestination(getWorkerGroup(record));
      if (via !== '紹介') {
        return false;
      }
      const owner = String(getWorkerIntroducer(record) || '').trim();
      if (!owner) {
        return false;
      }
      if (owner === targetKey || owner === targetLabel) {
        return true;
      }
      return (targetLabel && owner.includes(targetLabel)) || (targetKey && owner.includes(targetKey));
    });

    if (!introducedWorkers.length) {
      return { lineItems: [], summaryRows: [] };
    }

    const introducedIds = new Set(introducedWorkers.map((r) => getFieldValue(r, 'worker_id').trim()).filter(Boolean));
    const workerNameById = new Map();
    introducedWorkers.forEach((record) => {
      const id = getFieldValue(record, 'worker_id').trim();
      if (id) {
        workerNameById.set(id, getWorkerDisplayName(record) || id);
      }
    });

    const { workerCode, dateCode } = await resolveActualsFieldCodes();
    const range = toMonthRange(parsed.year, parsed.month);
    const query = `${dateCode} >= "${range.from}" and ${dateCode} <= "${range.to}" order by $id asc limit 500`;
    const actuals = await fetchRecords(CONFIG.apps.actuals, query, [workerCode, dateCode, 'hours', 'start_time', 'end_time', 'break_minutes']);

    const hoursByWorker = new Map();
    actuals.forEach((record) => {
      const id = getFieldValue(record, workerCode).trim();
      if (!id || !introducedIds.has(id)) {
        return;
      }
      const hours = calcActualHours(record);
      if (!Number.isFinite(hours) || hours <= 0) {
        return;
      }
      hoursByWorker.set(id, (hoursByWorker.get(id) || 0) + hours);
    });

    const rate = String(targetLabel || targetKey).includes('笠井') ? 1000 : 2000;
    const rows = Array.from(hoursByWorker.entries())
      .sort((a, b) => String(workerNameById.get(a[0]) || a[0]).localeCompare(String(workerNameById.get(b[0]) || b[0]), 'ja'))
      .map(([id, hours]) => {
        const roundedHours = Math.round(hours * 100) / 100;
        const amount = Math.round(roundedHours * rate);
        return {
          workerId: id,
          workerName: String(workerNameById.get(id) || id),
          name: `${String(workerNameById.get(id) || id)} 紹介手数料`.slice(0, 30),
          quantity: Number(roundedHours.toFixed(2)),
          unitPrice: rate,
          amount
        };
      });

    const summaryRows = rows.map((row) => ({
      workerId: row.workerId,
      workerName: row.workerName,
      quantity: row.quantity,
      amount: row.amount
    }));

    return {
      lineItems: rows.map((row) => ({
        name: row.name,
        quantity: row.quantity,
        unitPrice: row.unitPrice,
        amount: row.amount
      })),
      summaryRows
    };
  }

  async function buildIntroducerPayoutLineItems(periodKey, introducerKey, introducerName) {
    const detail = await buildIntroducerPayoutDetail(periodKey, introducerKey, introducerName);
    return detail.lineItems;
  }

  async function buildStaffPayoutDetail(periodKey, staffRecord, supportFeeNum) {
    const parsed = parsePeriodKey(periodKey);
    if (!parsed || !staffRecord) {
      return { lineItems: [], summaryRows: [] };
    }

    const staffId = getFieldValue(staffRecord, 'id').trim();
    const staffName = getFieldValue(staffRecord, 'name').trim();
    const role = getFieldValue(staffRecord, 'role').trim();
    if (!staffId) {
      return { lineItems: [], summaryRows: [] };
    }
    if (role.includes('事務')) {
      throw new Error('職員「事務」向けの支払明細は現在保留です');
    }

    const assignments = await fetchAssignmentList();
    const targetAssignments = (assignments || []).filter((record) => {
      const start = getFieldValue(record, 'start_date').trim();
      if (!start || start.length < 7) {
        return false;
      }
      const y = Number(start.slice(0, 4));
      const m = Number(start.slice(5, 7));
      return y === parsed.year && m === parsed.month;
    });

    const lineItems = [];
    const summaryRows = [];

    if (role.includes('全体')) {
      const salesTotal = targetAssignments.reduce((sum, record) => {
        const baseReward = parseAmountNumber(getFieldValue(record, 'base_reward'));
        const headcount = Math.max(parseAmountNumber(getFieldValue(record, 'headcount_required')) || 1, 1);
        return sum + Math.round(baseReward * headcount);
      }, 0);
      const amount = Math.round(salesTotal * 0.08);
      lineItems.push({
        name: '全体責任者 管理費(売上8%)',
        quantity: '一式',
        unitPrice: amount,
        amount
      });
      summaryRows.push({
        workerId: staffId,
        workerName: staffName || staffId,
        quantity: '売上8%',
        amount
      });
    } else if (role.includes('プレイングマネージャー')) {
      const workers = await fetchAllWorkers();
      const matchedWorker = (workers || []).find((row) => {
        const workerName = getWorkerDisplayName(row).trim();
        return workerName && staffName && workerName === staffName;
      });
      const playingWorkerId = matchedWorker ? getFieldValue(matchedWorker, 'worker_id').trim() : '';
      const managerCandidates = [String(staffId || '').trim(), playingWorkerId, String(staffName || '').trim()].filter(Boolean);
      if (managerCandidates.length === 0) {
        throw new Error('プレイングマネージャーの識別子が不足しています');
      }

      const groupedByArea = new Map();
      targetAssignments.forEach((record) => {
        const managerId = getFieldValue(record, 'playing_manager').trim();
        if (!managerCandidates.includes(managerId)) {
          return;
        }
        const area = extractAreaName(getFieldValue(record, 'address'));
        const headcount = Math.max(parseAmountNumber(getFieldValue(record, 'headcount_required')), 0);
        const hours = Math.max(parseAmountNumber(getFieldValue(record, 'work_hours')), 0);
        const manHours = headcount * hours;
        if (manHours <= 0) {
          return;
        }
        groupedByArea.set(area, (groupedByArea.get(area) || 0) + manHours);
      });

      Array.from(groupedByArea.keys()).sort((a, b) => a.localeCompare(b, 'ja')).forEach((area) => {
        const manHours = groupedByArea.get(area) || 0;
        const amount = Math.round(manHours * 1000);
        lineItems.push({
          name: `【${area}】稼働人工・管理費`,
          quantity: Number(manHours.toFixed(2)),
          unitPrice: 1000,
          amount
        });
        summaryRows.push({
          workerId: area,
          workerName: `${area} 稼働人工`,
          quantity: Number(manHours.toFixed(2)),
          amount
        });
      });
    }

    if (role.includes('プレイングマネージャー')) {
      const support = Math.max(parseAmountNumber(supportFeeNum || 0), 0);
      lineItems.push({
        name: '運営協力費',
        quantity: '一式',
        unitPrice: support,
        amount: support
      });
    }

    return { lineItems, summaryRows };
  }

  async function buildPayoutLineItems(periodKey, workerId) {
    const parsed = parsePeriodKey(periodKey);
    if (!parsed || !workerId) {
      return [];
    }

    const { workerCode, workerType, dateCode } = await resolveActualsFieldCodes();
    const range = toMonthRange(parsed.year, parsed.month);
    const workerCondition = buildKintoneFieldCondition(workerCode, workerType, workerId);
    const dummyItems = [
      { name: '東京_980飲食店(5h)', quantity: 8, unitPrice: 17280, amount: 138240 },
      { name: '┗インセンティブ', quantity: 0, unitPrice: 0, amount: 0 },
      { name: '東京_PloomLounge2名体制', quantity: 2, unitPrice: 17280, amount: 34560 },
      { name: '┗インセンティブ', quantity: 2, unitPrice: 2160, amount: 4320 },
      { name: '【WBF】稼働人工', quantity: '一式', unitPrice: 201960, amount: 201960 },
      { name: '【WBF】運営協力費', quantity: '一式', unitPrice: 18110, amount: 18110 },
      { name: '【SLS】稼働人工', quantity: '一式', unitPrice: 95040, amount: 95040 },
      { name: '【SLS】運営協力費', quantity: '一式', unitPrice: 32400, amount: 32400 }
    ];

    const query = `${workerCondition} and ${dateCode} >= "${range.from}" and ${dateCode} <= "${range.to}" order by $id asc limit 500`;
    let actuals = [];
    try {
      actuals = await fetchRecords(CONFIG.apps.actuals, query, [workerCode, dateCode, 'assignment_id']);
    } catch (err) {
      console.warn('実績取得に失敗したためダミー明細にフォールバックします:', err && err.message ? err.message : err);
      return dummyItems;
    }

    if (!actuals.length) {
      return dummyItems;
    }

    const assignments = await fetchAssignmentList();
    const assignmentMap = new Map();
    (assignments || []).forEach((record) => {
      const assignmentId = getFieldValue(record, 'assignment_id').trim();
      if (assignmentId) {
        assignmentMap.set(assignmentId, record);
      }
    });

    const grouped = new Map();
    actuals.forEach((actual) => {
      const assignmentId = getFieldValue(actual, 'assignment_id').trim();
      const assignment = assignmentMap.get(assignmentId);
      const area = assignment ? extractAreaName(getFieldValue(assignment, 'address')) : 'その他';
      const middle = assignment ? (getFieldValue(assignment, 'category_middle') || '未分類') : '未分類';
      const detail = assignment
        ? (getFieldValue(assignment, 'assignment_title') || getFieldValue(assignment, 'event_name') || assignmentId || '作業報酬')
        : (assignmentId || '作業報酬');
      const title = `${area}_${middle}：${detail}`;
      const unitPrice = assignment ? parseAmountNumber(getFieldValue(assignment, 'base_reward')) : 0;
      const key = `${assignmentId || title}`;
      if (!grouped.has(key)) {
        grouped.set(key, {
          name: title,
          quantity: 0,
          unitPrice,
          amount: 0
        });
      }
      const row = grouped.get(key);
      row.quantity += 1;
      row.amount = row.unitPrice > 0 ? row.unitPrice * row.quantity : 0;
    });

    const generated = Array.from(grouped.values()).map((item) => ({
      name: String(item.name || '作業報酬').slice(0, 30),
      quantity: item.quantity || 1,
      unitPrice: item.unitPrice || 0,
      amount: item.amount || 0
    }));
    const hasEnoughKinds = generated.length >= 4;
    const hasPositiveAmount = generated.some((item) => parseAmountNumber(item.amount) > 0);
    return (hasEnoughKinds && hasPositiveAmount) ? generated : dummyItems;
  }

  function downloadPdfBlob(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 5000);
  }

  async function uploadFileBlobToExternal(blob, fileName) {
    const endpoint = String((CONFIG.invoicePdf && CONFIG.invoicePdf.externalUploadUrl) || '').trim();
    if (!endpoint) {
      throw new Error('外部アップロード先が未設定です');
    }

    const formData = new FormData();
    formData.append('file', new File([blob], fileName, { type: 'application/pdf' }));
    formData.append('fileName', fileName);

    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
      credentials: 'omit'
    });

    if (!response.ok) {
      throw new Error(`外部アップロードに失敗しました: HTTP ${response.status}`);
    }

    let json = {};
    try {
      json = await response.json();
    } catch (e) {
      throw new Error('外部アップロード応答の解析に失敗しました');
    }

    const fileUrl = String((json && (json.fileUrl || json.url)) || '').trim();
    const fileId = String((json && (json.fileId || json.id || json.key)) || '').trim();
    if (!fileUrl && !fileId) {
      throw new Error('外部アップロード応答に識別子がありません');
    }
    return { fileUrl, fileId };
  }

  function uploadFileBlobToKintone(blob, fileName) {
    const getTokenCandidates = () => {
      const tokens = [];
      const pushUnique = (value) => {
        const token = String(value || '').trim();
        if (!token) {
          return;
        }
        if (tokens.indexOf(token) === -1) {
          tokens.push(token);
        }
      };

      try {
        pushUnique(kintone.getRequestToken());
      } catch (e) {
      }

      try {
        const el = document.querySelector('input[name="__REQUEST_TOKEN__"]');
        if (el && el.value) {
          pushUnique(el.value);
        }
      } catch (e) {
      }

      try {
        if (window.cybozu && window.cybozu.data && window.cybozu.data.REQUEST_TOKEN) {
          pushUnique(window.cybozu.data.REQUEST_TOKEN);
        }
      } catch (e) {
      }

      return tokens;
    };

    const uploadOnce = (requestToken) => {
      const formData = new FormData();
      formData.append('__REQUEST_TOKEN__', requestToken);
      const file = new File([blob], fileName, { type: 'application/pdf' });
      formData.append('file', file);

      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', buildQueryPath('file.json'), true);
        xhr.withCredentials = true;
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

        xhr.onload = () => {
          if (xhr.status < 200 || xhr.status >= 300) {
            reject(new Error(summarizeUploadError(xhr.status, xhr.responseText)));
            return;
          }
          try {
            const json = JSON.parse(xhr.responseText || '{}');
            if (!json || !json.fileKey) {
              reject(new Error('PDFアップロードに失敗しました（fileKey未取得）'));
              return;
            }
            resolve(String(json.fileKey));
          } catch (e) {
            reject(new Error('PDFアップロード応答の解析に失敗しました'));
          }
        };

        xhr.onerror = () => {
          reject(new Error('PDFアップロード通信に失敗しました'));
        };

        xhr.send(formData);
      });
    };

    const tokens = getTokenCandidates();
    if (!tokens.length) {
      return Promise.reject(new Error('CSRFトークンを取得できませんでした。ページを再読み込みしてください。'));
    }

    return tokens.reduce((chain, token) => {
      return chain.catch(() => uploadOnce(token));
    }, Promise.reject(new Error('PDFアップロード初期化'))).catch((error) => {
      throw error;
    });
  }

  function formatAmountDisplay(value) {
    const num = Number(String(value || '').replace(/,/g, ''));
    if (!Number.isFinite(num)) {
      return String(value || '0');
    }
    return num.toLocaleString('ja-JP');
  }

  function parseAmountNumber(value) {
    const num = Number(
      String(value == null ? '' : value)
        .replace(/[¥￥,，\s]/g, '')
        .trim()
    );
    return Number.isFinite(num) ? num : 0;
  }

  async function generateAndAttachInvoicePdf(invoiceFields, recordId, summary) {
    const recordResp = await kintone.api(buildQueryPath('record.json'), 'GET', {
      app: invoiceFields.appId,
      id: String(recordId)
    });
    const record = recordResp && recordResp.record ? recordResp.record : {};
    const invoiceId = invoiceFields.invoiceIdCode
      ? getFieldValue(record, invoiceFields.invoiceIdCode).trim()
      : '';
    const effectiveInvoiceId = invoiceId || `record_${recordId}`;

    const fixedOfficeFeeRaw = invoiceFields.fixedOfficeFeeCode
      ? getFieldValue(record, invoiceFields.fixedOfficeFeeCode).trim()
      : '';
    const summaryFixedOfficeFeeRaw = summary && Object.prototype.hasOwnProperty.call(summary, 'fixedOfficeFeeAmount')
      ? summary.fixedOfficeFeeAmount
      : '';
    const hasFixedOfficeFee = !!summary.hasFixedOfficeFee || String(summaryFixedOfficeFeeRaw || '').trim() !== '';
    const summaryFixedOfficeFeeNum = parseAmountNumber(summaryFixedOfficeFeeRaw || 0);
    const recordFixedOfficeFeeNum = parseAmountNumber(fixedOfficeFeeRaw || 0);
    const fixedOfficeFeeNum = hasFixedOfficeFee
      ? summaryFixedOfficeFeeNum
      : Math.max(summaryFixedOfficeFeeNum, recordFixedOfficeFeeNum);
    const addressee = await resolveInvoiceAddressee(summary.periodKey, summary.responsible, summary.clientCompany);
    const lineItems = await buildInvoiceLineItems(summary.periodKey, summary.responsible, fixedOfficeFeeNum, summary.clientCompany);
    const lineItemsTotal = lineItems.reduce((sum, item) => sum + parseAmountNumber(item.amount), 0);
    let subtotalNum = parseAmountNumber(getFieldValue(record, 'subtotal').trim());
    let taxAmountNum = parseAmountNumber(getFieldValue(record, 'tax_amount').trim());
    let totalAmountNum = parseAmountNumber(getFieldValue(record, 'total_amount').trim());
    const nonTaxAmountNum = 0;

    if (subtotalNum <= 0 && lineItemsTotal > 0) {
      subtotalNum = lineItemsTotal;
    }
    if (subtotalNum <= 0 && fixedOfficeFeeNum > 0) {
      subtotalNum = fixedOfficeFeeNum;
    }
    if (subtotalNum <= 0 && totalAmountNum > 0) {
      subtotalNum = Math.max(totalAmountNum - Math.max(taxAmountNum, 0), 0);
    }
    if (taxAmountNum <= 0 && subtotalNum > 0) {
      taxAmountNum = Math.floor(subtotalNum * 0.1);
    }
    if (taxAmountNum <= 0 && totalAmountNum > subtotalNum) {
      taxAmountNum = Math.max(totalAmountNum - subtotalNum, 0);
    }
    if (totalAmountNum <= 0 && subtotalNum > 0) {
      totalAmountNum = subtotalNum + Math.max(taxAmountNum, 0);
    }

    const fixedOfficeFee = formatAmountDisplay(fixedOfficeFeeNum);
    const subtotal = formatAmountDisplay(subtotalNum);
    const taxAmount = formatAmountDisplay(taxAmountNum);
    const totalAmount = formatAmountDisplay(totalAmountNum);

    const pdfBlob = await buildInvoicePdfBlob({
      periodKey: summary.periodKey,
      documentType: summary.documentType,
      responsible: summary.responsible,
      addressee,
      subject: summary.subject,
      recordId: String(recordId),
      invoiceId: effectiveInvoiceId,
      registrationNumber: summary.registrationNumber || 'T2011201021906',
      fixedOfficeFee,
      subtotal,
      taxAmount,
      totalAmount,
      nonTaxAmount: formatAmountDisplay(nonTaxAmountNum),
      lineItems
    });

    const fileName = sanitizeFileName(`${summary.periodKey}_${summary.documentType}_${summary.responsible}_${effectiveInvoiceId}.pdf`);

    const uploadTarget = String((CONFIG.invoicePdf && CONFIG.invoicePdf.uploadTarget) || 'external').trim();

    if (uploadTarget === 'external') {
      try {
        const externalResult = await uploadFileBlobToExternal(pdfBlob, fileName);
        const externalUrl = String(externalResult.fileUrl || '').trim();
        if (externalUrl && invoiceFields.pdfUrlCode) {
          await kintone.api(buildQueryPath('record.json'), 'PUT', {
            app: invoiceFields.appId,
            id: String(recordId),
            record: {
              [invoiceFields.pdfUrlCode]: {
                value: externalUrl
              }
            }
          });
        }
        return {
          fileName,
          storage: 'external',
          fileUrl: externalUrl,
          fileId: externalResult.fileId || '',
          attachedToKintone: false,
          urlSaved: !!(externalUrl && invoiceFields.pdfUrlCode)
        };
      } catch (externalError) {
        downloadPdfBlob(pdfBlob, fileName);
        throw new Error(
          `外部ストレージへの自動保存に失敗しました（${externalError.message}）。\n` +
          `PDFファイル「${fileName}」を保存しました。アップロード先の設定を確認してください。`
        );
      }
    }

    if (uploadTarget === 'download') {
      downloadPdfBlob(pdfBlob, fileName);
      return {
        fileName,
        storage: 'download',
        fileUrl: '',
        fileId: '',
        attachedToKintone: false,
        urlSaved: false
      };
    }

    if (!invoiceFields.attachmentCode) {
      downloadPdfBlob(pdfBlob, fileName);
      throw new Error('請求書アプリにPDF添付フィールドが見つかりません（FILEフィールドが必要です）');
    }

    let newFileKey = '';
    try {
      newFileKey = await uploadFileBlobToKintone(pdfBlob, fileName);
    } catch (uploadErr) {
      downloadPdfBlob(pdfBlob, fileName);
      throw new Error(
        `PDF自動添付に失敗しました（${uploadErr.message}）。\n` +
        `PDFファイル「${fileName}」を保存しました。レコード詳細画面で手動添付してください。`
      );
    }

    const existingFiles = (record[invoiceFields.attachmentCode] && record[invoiceFields.attachmentCode].value) || [];
    const merged = existingFiles
      .filter((item) => item && item.fileKey)
      .map((item) => ({ fileKey: String(item.fileKey) }));
    merged.push({ fileKey: newFileKey });

    await kintone.api(buildQueryPath('record.json'), 'PUT', {
      app: invoiceFields.appId,
      id: String(recordId),
      record: {
        [invoiceFields.attachmentCode]: {
          value: merged
        }
      }
    });

    return {
      fileName,
      storage: 'kintone',
      fileKey: newFileKey,
      fileUrl: '',
      fileId: '',
      attachedToKintone: true,
      urlSaved: false
    };
  }

  async function generateAndAttachPayoutPdf(payoutFields, recordId, options) {
    const opts = options || {};
    const recordResp = await kintone.api(buildQueryPath('record.json'), 'GET', {
      app: payoutFields.appId,
      id: String(recordId)
    });
    const record = recordResp && recordResp.record ? recordResp.record : {};

    const periodKey = payoutFields.periodCode ? getFieldValue(record, payoutFields.periodCode).trim() : '';
    const originalWorkerId = payoutFields.workerCode ? getFieldValue(record, payoutFields.workerCode).trim() : '';
    const workerId = String(opts.workerId || originalWorkerId || '').trim();
    const supplierId = payoutFields.supplierCode ? getFieldValue(record, payoutFields.supplierCode).trim() : '';
    const payoutId = payoutFields.payoutIdCode
      ? (getFieldValue(record, payoutFields.payoutIdCode).trim() || `PD-${periodKey || '000000'}-${workerId || 'UNKNOWN'}`)
      : `PD-${periodKey || '000000'}-${workerId || 'UNKNOWN'}`;
    const paymentDate = payoutFields.paymentDateCode
      ? (getFieldValue(record, payoutFields.paymentDateCode).trim() || computePayoutPaymentDate(periodKey))
      : computePayoutPaymentDate(periodKey);
    const closeDate = payoutFields.closedAtCode
      ? (getFieldValue(record, payoutFields.closedAtCode).trim() || computePayoutCloseDate(periodKey))
      : computePayoutCloseDate(periodKey);

    const patchRecord = {};
    if (payoutFields.paymentDateCode && !getFieldValue(record, payoutFields.paymentDateCode).trim() && paymentDate) {
      patchRecord[payoutFields.paymentDateCode] = { value: paymentDate };
    }
    if (payoutFields.closedAtCode && !getFieldValue(record, payoutFields.closedAtCode).trim() && closeDate) {
      patchRecord[payoutFields.closedAtCode] = { value: closeDate };
    }
    if (Object.keys(patchRecord).length) {
      await kintone.api(buildQueryPath('record.json'), 'PUT', {
        app: payoutFields.appId,
        id: String(recordId),
        record: patchRecord
      });
    }
    const workerName = await (async () => {
      if (opts.workerName) {
        return String(opts.workerName).trim();
      }
      if (supplierId) {
        const suppliers = SUPPLIERS_CACHE || [];
        const supplier = suppliers.find((row) => {
          const id = getFieldValue(row, 'supplier_id').trim() || getFieldValue(row, 'corporate_worker_id').trim();
          return id === supplierId;
        });
        const supplierName = supplier ? (getFieldValue(supplier, 'company_name').trim() || supplierId) : '';
        if (supplierName) {
          return supplierName;
        }
      }
      const resolvedName = await resolveWorkerDisplayNameByAnyId(originalWorkerId || workerId);
      if (resolvedName) {
        return resolvedName;
      }
      const parsed = parsePeriodKey(periodKey);
      if (parsed) {
        const actualNameMap = await fetchActualWorkerNamesByPeriod(parsed.year, parsed.month);
        const actualName = String(actualNameMap[String(originalWorkerId || workerId).trim()] || '').trim();
        if (actualName) {
          return actualName;
        }
      }
      return workerId;
    })();
    const hasOverrideLineItems = Array.isArray(opts.lineItems) && opts.lineItems.length > 0;
    let normalLineItems = [];
    let introducerDetail = { lineItems: [], summaryRows: [] };
    if (!hasOverrideLineItems) {
      normalLineItems = await buildPayoutLineItems(periodKey, originalWorkerId || workerId);
      introducerDetail = await buildIntroducerPayoutDetail(periodKey, supplierId || workerId, workerName);
    }
    const introducerLineItems = introducerDetail.lineItems;
    const lineItems = hasOverrideLineItems
      ? opts.lineItems
      : (introducerLineItems.length ? introducerLineItems : normalLineItems);
    const summaryRows = Array.isArray(opts.summaryRows) ? opts.summaryRows : introducerDetail.summaryRows;
    const totalAmount = lineItems.reduce((sum, item) => sum + parseAmountNumber(item.amount), 0) || parseAmountNumber(getFieldValue(record, 'total_amount').trim() || 0);
    const note = (opts.note != null)
      ? String(opts.note)
      : (payoutFields.noteCode ? getFieldValue(record, payoutFields.noteCode).trim() : '');

    const pdfBlob = await buildPayoutPdfBlob({
      periodKey,
      workerId,
      workerName,
      payoutId,
      paymentDate,
      totalAmount,
      note,
      withholdingTax: opts.withholdingTax,
      summaryRows,
      lineItems,
      recordId: String(recordId)
    });

    const fileName = sanitizeFileName(`${periodKey || '000000'}_${workerId || 'worker'}_${payoutId}_支払明細.pdf`);
    downloadPdfBlob(pdfBlob, fileName);
    const uploadTarget = String((CONFIG.payoutPdf && CONFIG.payoutPdf.uploadTarget) || 'kintone').trim();

    if (uploadTarget === 'external') {
      const endpointBackup = CONFIG.invoicePdf.externalUploadUrl;
      if (CONFIG.payoutPdf && CONFIG.payoutPdf.externalUploadUrl) {
        CONFIG.invoicePdf.externalUploadUrl = CONFIG.payoutPdf.externalUploadUrl;
      }
      try {
        const externalResult = await uploadFileBlobToExternal(pdfBlob, fileName);
        const externalUrl = String(externalResult.fileUrl || '').trim();
        if (externalUrl && payoutFields.pdfUrlCode) {
          await kintone.api(buildQueryPath('record.json'), 'PUT', {
            app: payoutFields.appId,
            id: String(recordId),
            record: {
              [payoutFields.pdfUrlCode]: {
                value: externalUrl
              }
            }
          });
        }
        return {
          fileName,
          storage: 'external',
          fileUrl: externalUrl,
          attachedToKintone: false,
          urlSaved: !!(externalUrl && payoutFields.pdfUrlCode)
        };
      } finally {
        CONFIG.invoicePdf.externalUploadUrl = endpointBackup;
      }
    }

    if (uploadTarget === 'download') {
      downloadPdfBlob(pdfBlob, fileName);
      return {
        fileName,
        storage: 'download',
        fileUrl: '',
        attachedToKintone: false,
        urlSaved: false
      };
    }

    if (!payoutFields.attachmentCode) {
      downloadPdfBlob(pdfBlob, fileName);
      throw new Error('支払明細アプリにPDF添付フィールドが見つかりません（FILEフィールドが必要です）');
    }

    const newFileKey = await uploadFileBlobToKintone(pdfBlob, fileName);
    const existingFiles = (record[payoutFields.attachmentCode] && record[payoutFields.attachmentCode].value) || [];
    const merged = existingFiles
      .filter((item) => item && item.fileKey)
      .map((item) => ({ fileKey: String(item.fileKey) }));
    merged.push({ fileKey: newFileKey });

    await kintone.api(buildQueryPath('record.json'), 'PUT', {
      app: payoutFields.appId,
      id: String(recordId),
      record: {
        [payoutFields.attachmentCode]: {
          value: merged
        }
      }
    });

    return {
      fileName,
      storage: 'kintone',
      fileKey: newFileKey,
      fileUrl: '',
      attachedToKintone: true,
      urlSaved: false
    };
  }

  function openUploadedPdfInNewTab(fileKey) {
    const key = String(fileKey || '').trim();
    if (!key) {
      return;
    }
    const url = `${buildQueryPath('file.json')}?fileKey=${encodeURIComponent(key)}`;
    try {
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      // noop
    }
  }

  function fetchResponsibleNames() {
    return Promise.all([fetchStaffManagers(), fetchAssignmentList()]).then(([staffRecords, assignmentRecords]) => {
      const names = new Set();
      (staffRecords || []).forEach((record) => {
        const name = record && record.name && record.name.value ? String(record.name.value).trim() : '';
        if (name) {
          names.add(name);
        }
      });
      (assignmentRecords || []).forEach((record) => {
        const owner = record && record.owner_name && record.owner_name.value ? String(record.owner_name.value).trim() : '';
        if (owner) {
          names.add(owner);
        }
      });
      return Array.from(names).sort();
    });
  }

  function fetchActualWorkerIdsByPeriod(year, month) {
    const periodKey = toPeriodKey(year, month);
    if (ACTUAL_WORKER_IDS_BY_PERIOD_CACHE[periodKey]) {
      return Promise.resolve(ACTUAL_WORKER_IDS_BY_PERIOD_CACHE[periodKey]);
    }

    return resolveActualsFieldCodes().then(({ workerCode, dateCode }) => {
      const range = toMonthRange(year, month);
      const query = `${dateCode} >= "${range.from}" and ${dateCode} <= "${range.to}" order by $id asc limit 500`;
      console.log('[fetchActualWorkerIdsByPeriod] workerCode:', workerCode, 'query:', query);
      // フィールド絞りなし → 実績アプリの全フィールドを取得してデバッグ
      return fetchRecords(CONFIG.apps.actuals, query).then((records) => {
        const workerIdSet = new Set();
        records.forEach((record) => {
          const workerId = getFieldValue(record, workerCode).trim();
          if (workerId) {
            workerIdSet.add(workerId);
          }
        });
        const ids = Array.from(workerIdSet).sort();
        console.log('[fetchActualWorkerIdsByPeriod] 取得IDs:', ids);
        // 先頭レコードの全フィールド（値）をログ出力 → 実績アプリの構造を把握するため
        if (records.length > 0) {
          const sampleRec = records[0];
          const sampleFields = {};
          Object.keys(sampleRec || {}).forEach((k) => {
            const v = getFieldValue(sampleRec, k);
            if (v) sampleFields[k] = v;
          });
          console.log('[fetchActualWorkerIdsByPeriod] 実績先頭レコード（値あり）:', sampleFields);
          console.log('[fetchActualWorkerIdsByPeriod] 実績先頭レコード（全キー）:', Object.keys(sampleRec || {}));
          // USER_SELECT型など value が配列になるフィールドを生JSOで確認
          console.log('[fetchActualWorkerIdsByPeriod] 作業者フィールド生データ:', JSON.stringify(sampleRec['作業者'] || null));
          console.log('[fetchActualWorkerIdsByPeriod] worker_idフィールド生データ:', JSON.stringify(sampleRec['worker_id'] || null));
        }
        ACTUAL_WORKER_IDS_BY_PERIOD_CACHE[periodKey] = ids;
        return ids;
      });
    });
  }

  function fetchActualWorkerNamesByPeriod(year, month) {
    const periodKey = toPeriodKey(year, month);
    if (ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE[periodKey]) {
      return Promise.resolve(ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE[periodKey]);
    }

    return resolveActualsFieldCodes().then(({ workerCode, dateCode, workerNameCode, lastNameCode, firstNameCode, workerIdLabelMap }) => {
      const range = toMonthRange(year, month);
      const query = `${dateCode} >= "${range.from}" and ${dateCode} <= "${range.to}" order by $id asc limit 500`;
      console.log('[fetchActualWorkerNamesByPeriod] workerCode:', workerCode, 'dropdownMapSize:', Object.keys(workerIdLabelMap || {}).length);

      // ① DROP_DOWN options から直接マップが作れる場合はそれを使う（最速・最確実）
      if (workerIdLabelMap && Object.keys(workerIdLabelMap).length > 0) {
        console.log('[fetchActualWorkerNamesByPeriod] DROP_DOWN optionsマップを使用');
        ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE[periodKey] = workerIdLabelMap;
        return Promise.resolve(workerIdLabelMap);
      }

      // レコードから名前を取り出すユーティリティ
      // USER_SELECT型: {type:'USER_SELECT', value:[{code:'user1',name:'田中太郎'},...]}
      // SINGLE_LINE_TEXT型: {type:'SINGLE_LINE_TEXT', value:'田中太郎'}
      const extractNameFromField = (fieldObj) => {
        if (!fieldObj) return '';
        // USER_SELECT / GROUP_SELECT / ORGANIZATION_SELECT など value が配列のもの
        if (Array.isArray(fieldObj.value)) {
          const names = fieldObj.value.map((u) => String(u && u.name ? u.name : '')).filter(Boolean);
          return names.join(', ');
        }
        return String(fieldObj.value || '').trim();
      };

      const buildMapFromRecords = (records) => {
        const map = {};
        const nameCandidates = [
          workerNameCode, lastNameCode, firstNameCode,
          'worker_name', 'name', 'full_name', 'staff_name',
          'worker_full_name', 'worker', 'last_name', 'first_name', 'member_name'
        ].filter((code) => code && code !== workerCode);

        (records || []).forEach((record) => {
          const workerId = getFieldValue(record, workerCode).trim();
          if (!workerId) return;
          if (map[workerId]) return; // 既に取得済み

          let workerName = '';

          // ① 作業者フィールド（USER_SELECT型）を最優先で試みる
          const sakusha = record['作業者'];
          if (sakusha) {
            workerName = extractNameFromField(sakusha);
          }

          // ② 姓名結合
          if (!workerName && lastNameCode && firstNameCode) {
            const ln = getFieldValue(record, lastNameCode).trim();
            const fn = getFieldValue(record, firstNameCode).trim();
            if (ln || fn) workerName = `${ln} ${fn}`.trim();
          }

          // ③ 名前候補フィールドを順番に試す
          if (!workerName) {
            for (const code of nameCandidates) {
              if (!code || !record[code]) continue;
              const v = extractNameFromField(record[code]);
              if (v) { workerName = v; break; }
            }
          }

          // ④ 全フィールドから USER_SELECT 型を探す
          if (!workerName) {
            for (const code of Object.keys(record || {})) {
              const f = record[code];
              if (!f || !Array.isArray(f.value) || !f.value.length) continue;
              const names = f.value.map((u) => String(u && u.name ? u.name : '')).filter(Boolean);
              if (names.length) { workerName = names.join(', '); break; }
            }
          }

          // ⑤ フィールドコードに "name" を含むものを全フィールドから探す
          if (!workerName) {
            for (const code of Object.keys(record || {})) {
              const lower = code.toLowerCase();
              if (!lower.includes('name') || lower.includes('id')) continue;
              const v = extractNameFromField(record[code]);
              if (v) { workerName = v; break; }
            }
          }

          if (workerName) map[workerId] = workerName;
        });

        if (Object.keys(map).length === 0 && records && records.length > 0) {
          const sampleRec = records[0];
          const rawSample = {};
          Object.keys(sampleRec || {}).forEach((k) => { rawSample[k] = JSON.stringify(sampleRec[k]); });
          console.warn('[fetchActualWorkerNamesByPeriod] 名前フィールド未発見。先頭レコード生データ:', rawSample);
        } else {
          console.log('[fetchActualWorkerNamesByPeriod] 名前マップ:', map);
        }
        return map;
      };

      // ② App158（アサインアプリ）経由でULID→WRK番号→氏名の2段階ルックアップ
      // 実績アプリのassignment_idからApp158のworker_id(WRK形式)を引き、App165から名前を取得
      const tryAssignmentLookup = (actualsRecords) => {
        // ULID→assignment_id の対応マップ
        const ulidToAssignmentId = {};
        const allAssignmentIds = [];
        (actualsRecords || []).forEach((record) => {
          const ulid = getFieldValue(record, workerCode).trim();
          const assignId = getFieldValue(record, 'assignment_id').trim();
          if (ulid && assignId && !ulidToAssignmentId[ulid]) {
            ulidToAssignmentId[ulid] = assignId;
            allAssignmentIds.push(assignId);
          }
        });
        if (!allAssignmentIds.length) {
          console.warn('[fetchActualWorkerNamesByPeriod] assignment_id未取得');
          return Promise.resolve({});
        }
        const uniqueAssignIds = Array.from(new Set(allAssignmentIds));
        console.log('[fetchActualWorkerNamesByPeriod] assignment_id経由ルックアップ:', uniqueAssignIds.length, '件');

        // App158からassignment_id でwrk番号を引く
        const chunks = [];
        for (let i = 0; i < uniqueAssignIds.length; i += 100) {
          chunks.push(uniqueAssignIds.slice(i, i + 100));
        }
        return Promise.all(chunks.map((chunk) => {
          const inVals = chunk.map((id) => `"${escapeKintoneQueryValue(id)}"`).join(',');
          return fetchRecords(
            CONFIG.apps.assignments,
            `assignment_id in (${inVals}) order by $id asc limit 500`,
            ['assignment_id', 'worker_id']
          ).catch(() => []);
        })).then((results) => {
          const assignRows = results.reduce((acc, rows) => acc.concat(rows || []), []);
          // assignment_id → worker_id(WRK形式) マップ
          const assignmentToWrk = {};
          assignRows.forEach((record) => {
            const assignId = getFieldValue(record, 'assignment_id').trim();
            const wrkId = getFieldValue(record, 'worker_id').trim();
            if (assignId && wrkId) assignmentToWrk[assignId] = wrkId;
          });
          console.log('[fetchActualWorkerNamesByPeriod] App158からWRK取得:', Object.keys(assignmentToWrk).length, '件');

          // WRK番号のリスト
          const wrkIds = Array.from(new Set(Object.values(assignmentToWrk)));
          if (!wrkIds.length) return {};

          // App165からWRK番号で名前を取得
          const wrkChunks = [];
          for (let i = 0; i < wrkIds.length; i += 100) {
            wrkChunks.push(wrkIds.slice(i, i + 100));
          }
          return Promise.all(wrkChunks.map((chunk) => {
            const inVals = chunk.map((id) => `"${escapeKintoneQueryValue(id)}"`).join(',');
            return fetchRecords(
              CONFIG.apps.workers,
              `worker_id in (${inVals}) order by $id asc limit 500`,
              ['worker_id', 'last_name', 'first_name']
            ).catch(() => []);
          })).then((wrkResults) => {
            const wrkRows = wrkResults.reduce((acc, rows) => acc.concat(rows || []), []);
            // WRK → 氏名 マップ
            const wrkToName = {};
            wrkRows.forEach((record) => {
              const wrkId = getFieldValue(record, 'worker_id').trim();
              const lastName = getFieldValue(record, 'last_name').trim();
              const firstName = getFieldValue(record, 'first_name').trim();
              const name = `${lastName} ${firstName}`.trim();
              if (wrkId && name) wrkToName[wrkId] = name;
            });
            console.log('[fetchActualWorkerNamesByPeriod] App165から氏名取得:', Object.keys(wrkToName).length, '件');

            // ULID → 氏名 の最終マップを構築
            const finalMap = {};
            Object.keys(ulidToAssignmentId).forEach((ulid) => {
              const assignId = ulidToAssignmentId[ulid];
              const wrkId = assignmentToWrk[assignId];
              const name = wrkId ? wrkToName[wrkId] : '';
              if (name) finalMap[ulid] = name;
            });
            console.log('[fetchActualWorkerNamesByPeriod] ULID→氏名最終マップ:', finalMap);
            return finalMap;
          });
        });
      };

      // 全フィールドを取得してassignment_id経由でルックアップ
      return fetchRecords(CONFIG.apps.actuals, query).then((records) => {
        // まず従来方式（名前フィールドがある場合）を試みる
        const directMap = buildMapFromRecords(records);
        if (Object.keys(directMap).length > 0) {
          ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE[periodKey] = directMap;
          return directMap;
        }
        // 直接名前が取れない場合はassignment_id経由でルックアップ
        return tryAssignmentLookup(records).then((map) => {
          ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE[periodKey] = map;
          return map;
        });
      }).catch((e) => {
        console.warn('[fetchActualWorkerNamesByPeriod] エラー:', e);
        ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE[periodKey] = {};
        return {};
      });
    });
  }

  function fetchWorkerOptionsByIds(workerIds) {
    if (!workerIds || !workerIds.length) {
      return Promise.resolve([]);
    }
    const normalizedIds = Array.from(new Set(
      (workerIds || []).map((id) => String(id || '').trim()).filter(Boolean)
    ));
    if (!normalizedIds.length) {
      return Promise.resolve([]);
    }

    const chunkSize = 100;
    const normalizeIdentityRaw = (value) => String(value || '').trim();
    const normalizeIdentityLower = (value) => normalizeIdentityRaw(value).toLowerCase();
    const normalizeIdentityAlnum = (value) => normalizeIdentityLower(value).replace(/[^a-z0-9]/g, '');
    const buildIdentityKeys = (value) => {
      const raw = normalizeIdentityRaw(value);
      if (!raw) {
        return [];
      }
      const keys = [raw, normalizeIdentityLower(raw), normalizeIdentityAlnum(raw)].filter(Boolean);
      return Array.from(new Set(keys));
    };
    const toChunks = (ids) => {
      const chunks = [];
      for (let i = 0; i < ids.length; i += chunkSize) {
        chunks.push(ids.slice(i, i + chunkSize));
      }
      return chunks;
    };

    const fetchWorkersByField = (fieldCode, ids, fieldType) => {
      if (!fieldCode || !ids || !ids.length) {
        return Promise.resolve([]);
      }
      // SINGLE_LINE_TEXT / NUMBER など "in" 演算子が使えない型は "=" の OR 結合で検索する
      const useInOperator = !fieldType || /^(DROP_DOWN|RADIO_BUTTON|MULTI_SELECT|CHECK_BOX|USER_SELECT|STATUS)$/.test(String(fieldType).toUpperCase());
      const buildChunkQuery = (chunk) => {
        if (useInOperator) {
          const inValues = chunk.map((id) => `"${escapeKintoneQueryValue(id)}"`).join(',');
          return `${fieldCode} in (${inValues}) order by $id asc limit 500`;
        }
        // テキスト型では = と or を組み合わせる
        const orParts = chunk.map((id) => `${fieldCode} = "${escapeKintoneQueryValue(id)}"`).join(' or ');
        return `(${orParts}) order by $id asc limit 500`;
      };
      return Promise.all(toChunks(ids).map((chunk) => {
        const query = buildChunkQuery(chunk);
        return fetchRecords(CONFIG.apps.workers, query).catch(() => []);
      })).then((results) => results.reduce((acc, rows) => acc.concat(rows || []), []));
    };

    const fetchWorkersByRecordNo = (ids) => {
      const numericIds = (ids || []).map((id) => String(id || '').trim()).filter((id) => /^\d+$/.test(id));
      if (!numericIds.length) {
        return Promise.resolve([]);
      }
      return Promise.all(toChunks(numericIds).map((chunk) => {
        const inValues = chunk.map((id) => String(Number(id))).join(',');
        const query = `$id in (${inValues}) order by $id asc limit 500`;
        return fetchRecords(CONFIG.apps.workers, query);
      })).then((results) => results.reduce((acc, rows) => acc.concat(rows || []), []));
    };

    const buildOptionMap = (records, keyCode) => {
      const map = new Map();
      (records || []).forEach((record) => {
        // keyCode で値を取得、空の場合は worker_id でもリトライ
        let key = getFieldValue(record, keyCode).trim();
        if (!key && keyCode !== 'worker_id') {
          key = getFieldValue(record, 'worker_id').trim();
        }
        if (!key) {
          return;
        }
        map.set(key, {
          name: getWorkerDisplayName(record) || getFieldValue(record, 'worker_id').trim() || key,
          isIntroducer: normalizeViaDestination(getWorkerGroup(record)) === '紹介',
          resolved: true
        });
      });
      return map;
    };

    return resolveWorkerFieldCodes().then(async () => {
      const optionMap = new Map();

      // ① 実績アプリの worker_id DROP_DOWN options から直接名前を解決（最速）
      try {
        const { workerIdLabelMap } = await resolveActualsFieldCodes();
        if (workerIdLabelMap && Object.keys(workerIdLabelMap).length > 0) {
          normalizedIds.forEach((id) => {
            const label = workerIdLabelMap[id];
            if (label) {
              optionMap.set(id, { name: label, isIntroducer: false, resolved: true });
            }
          });
          console.log('[fetchWorkerOptionsByIds] DROP_DOWNオプションで解決:', optionMap.size, '/', normalizedIds.length);
          const stillUnresolved = normalizedIds.filter((id) => !optionMap.has(id));
          if (!stillUnresolved.length) {
            return normalizedIds.map((workerId) => {
              const row = optionMap.get(workerId);
              return { id: workerId, name: row ? row.name : workerId, isIntroducer: false, resolved: !!row };
            });
          }
        }
      } catch (e) { /* DROP_DOWN解決失敗は無視してApp165フォールバックへ */ }

      // App165の稼働者マスタを全件ロードしてインデックスを構築
      const workersForIndex = await fetchAllWorkers().catch((e) => {
        console.warn('[fetchWorkerOptionsByIds] fetchAllWorkers失敗:', e);
        return [];
      });
      console.log('[fetchWorkerOptionsByIds] App165レコード数:', (workersForIndex || []).length, '検索ID:', normalizedIds);
      const identityIndex = new Map();

      const candidateCodes = (WORKER_FIELD_CODES_CACHE && Array.isArray(WORKER_FIELD_CODES_CACHE.idCandidateCodes))
        ? WORKER_FIELD_CODES_CACHE.idCandidateCodes
        : ['worker_id', 'id', 'worker_ulid', 'worker_uuid', 'worker_key'];
      const indexCodes = Array.from(new Set(['worker_id', '$id'].concat(candidateCodes)));

      // ULID/UUID のようなランダム英数字パターン（20〜32文字）に一致するか判定
      const isUlidLike = (v) => /^[0-9A-Za-z]{20,32}$/.test(String(v || '').trim());

      // 先頭レコードで ULID 形式の値を持つフィールドを発見してインデックスコードに追加
      // （App165のworker_idが"WRK0001"形式で、実績アプリには別フィールドのULIDが入っているケースに対応）
      const ulidFieldSet = new Set(indexCodes);
      if (workersForIndex && workersForIndex.length > 0) {
        const sampleRecord = workersForIndex[0];
        Object.keys(sampleRecord || {}).forEach((code) => {
          if (code === '$id' || code === '$revision') return;
          const val = getFieldValue(sampleRecord, code).trim();
          if (val && isUlidLike(val)) {
            if (!ulidFieldSet.has(code)) {
              console.log('[fetchWorkerOptionsByIds] ULID形式フィールド発見:', code, '=', val);
              ulidFieldSet.add(code);
            }
          }
        });
      }
      const allIndexCodes = Array.from(ulidFieldSet);

      (workersForIndex || []).forEach((record) => {
        if (!record) {
          return;
        }
        allIndexCodes.forEach((code) => {
          const value = code === '$id'
            ? (record.$id && record.$id.value ? String(record.$id.value) : '')
            : getFieldValue(record, code).trim();
          buildIdentityKeys(value).forEach((key) => {
            if (!identityIndex.has(key)) {
              identityIndex.set(key, record);
            }
          });
        });
        // さらに全フィールドをフルスキャンして ULID 形式の値をインデックスに追加
        // （サンプルで未発見だったフィールドもカバー）
        Object.keys(record || {}).forEach((code) => {
          if (code === '$id' || code === '$revision' || ulidFieldSet.has(code)) return;
          const val = getFieldValue(record, code).trim();
          if (val && isUlidLike(val)) {
            buildIdentityKeys(val).forEach((key) => {
              if (!identityIndex.has(key)) {
                identityIndex.set(key, record);
              }
            });
          }
        });
      });
      console.log('[fetchWorkerOptionsByIds] identityIndexサイズ:', identityIndex.size);
      // デバッグ: 検索対象IDがインデックスに存在するか確認
      normalizedIds.forEach((id) => {
        const keys = buildIdentityKeys(id);
        const hit = keys.some((k) => identityIndex.has(k));
        if (!hit) {
          console.warn('[fetchWorkerOptionsByIds] インデックス不一致 ID:', id, 'キー試行:', keys);
        }
      });

      normalizedIds.forEach((id) => {
        const found = buildIdentityKeys(id).map((key) => identityIndex.get(key)).find((record) => !!record);
        if (!found) {
          return;
        }
        optionMap.set(id, {
          name: getWorkerDisplayName(found) || getFieldValue(found, 'worker_id').trim() || id,
          isIntroducer: normalizeViaDestination(getWorkerGroup(found)) === '紹介',
          resolved: true
        });
      });

      let unresolvedIds = normalizedIds.filter((id) => !optionMap.has(id));
      console.log('[fetchWorkerOptionsByIds] インデックス照合後 解決済み:', normalizedIds.length - unresolvedIds.length, '未解決:', unresolvedIds.length);
      if (!unresolvedIds.length) {
        return normalizedIds.map((workerId) => {
          const row = optionMap.get(workerId);
          return {
            id: workerId,
            name: row ? row.name : workerId,
            isIntroducer: row ? row.isIntroducer : false,
            resolved: !!row
          };
        });
      }

      const primaryRecords = await fetchWorkersByField('worker_id', unresolvedIds, 'SINGLE_LINE_TEXT');
      console.log('[fetchWorkerOptionsByIds] worker_idクエリ結果:', primaryRecords.length, '件, 未解決ID:', unresolvedIds);
      const primaryMap = buildOptionMap(primaryRecords, 'worker_id');
      unresolvedIds.forEach((id) => {
        const row = primaryMap.get(id);
        if (row) {
          optionMap.set(id, row);
        }
      });
      unresolvedIds = unresolvedIds.filter((id) => !optionMap.has(id));

      // ULID形式フィールド（サンプルスキャンで発見済み）に対してもクエリ検索
      for (const ulidCode of Array.from(ulidFieldSet)) {
        if (!ulidCode || ulidCode === 'worker_id' || ulidCode === '$id' || unresolvedIds.length === 0) continue;
        try {
          const ulidRecords = await fetchWorkersByField(ulidCode, unresolvedIds, 'SINGLE_LINE_TEXT');
          if (ulidRecords.length) {
            console.log('[fetchWorkerOptionsByIds] ULIDフィールド', ulidCode, 'クエリ結果:', ulidRecords.length, '件');
            const ulidMap = buildOptionMap(ulidRecords, ulidCode);
            unresolvedIds.forEach((id) => {
              const row = ulidMap.get(id);
              if (row) optionMap.set(id, row);
            });
            unresolvedIds = unresolvedIds.filter((id) => !optionMap.has(id));
          }
        } catch (e) { /* ignore */ }
      }

      for (let i = 0; i < normalizedIds.length; i += 1) {
        const id = normalizedIds[i];
        if (!optionMap.has(id) && identityIndex.has(id)) {
          const found = identityIndex.get(id);
          optionMap.set(id, {
            name: getWorkerDisplayName(found) || getFieldValue(found, 'worker_id').trim() || id,
            isIntroducer: normalizeViaDestination(getWorkerGroup(found)) === '紹介',
            resolved: true
          });
        }
      }
      unresolvedIds = normalizedIds.filter((id) => !optionMap.has(id));

      const candidateCodes2 = (WORKER_FIELD_CODES_CACHE && Array.isArray(WORKER_FIELD_CODES_CACHE.idCandidateCodes))
        ? WORKER_FIELD_CODES_CACHE.idCandidateCodes
        : ['worker_id', 'id', 'worker_ulid', 'worker_uuid', 'worker_key'];

      for (let i = 0; i < candidateCodes2.length; i += 1) {
        const code = candidateCodes2[i];
        if (!code || code === 'worker_id' || unresolvedIds.length === 0) {
          continue;
        }
        try {
          // idCandidateCodes のフィールドもテキスト型として OR 結合クエリで検索
          const altRecords = await fetchWorkersByField(code, unresolvedIds, 'SINGLE_LINE_TEXT');
          const altMap = buildOptionMap(altRecords, code);
          unresolvedIds.forEach((id) => {
            const row = altMap.get(id);
            if (row) {
              optionMap.set(id, row);
            }
          });
          unresolvedIds = unresolvedIds.filter((id) => !optionMap.has(id));
        } catch (e) {
        }
      }

      if (unresolvedIds.length > 0) {
        try {
          const byRecordNo = await fetchWorkersByRecordNo(unresolvedIds);
          const byRecordNoMap = buildOptionMap(byRecordNo, '$id');
          unresolvedIds.forEach((id) => {
            const row = byRecordNoMap.get(String(id));
            if (row) {
              optionMap.set(id, row);
            }
          });
        } catch (e) {
        }
      }

      if (unresolvedIds.length > 0) {
        try {
          unresolvedIds.forEach((id) => {
            const found = findWorkerRecordByIdentity(workersForIndex, id);
            if (found) {
              optionMap.set(id, {
                name: getWorkerDisplayName(found) || getFieldValue(found, 'worker_id').trim() || id,
                isIntroducer: normalizeViaDestination(getWorkerGroup(found)) === '紹介',
                resolved: true
              });
            }
          });
        } catch (e) {
        }
      }

      // ⑥ ULID形式IDがまだ未解決の場合はApp168のassignment_id→App158→App165の2段階ルックアップ
      unresolvedIds = normalizedIds.filter((id) => !optionMap.has(id));
      if (unresolvedIds.length > 0 && CONFIG.apps.assignments) {
        try {
          const isUlidLike2 = (v) => /^[0-9A-Za-z]{20,32}$/.test(String(v || '').trim());
          const ulidUnresolved = unresolvedIds.filter((id) => isUlidLike2(id));
          if (ulidUnresolved.length > 0) {
            console.log('[fetchWorkerOptionsByIds] ULID未解決→assignment_id経由ルックアップ:', ulidUnresolved);
            // App168からassignment_idを取得
            const ulidInVals = ulidUnresolved.map((id) => `"${escapeKintoneQueryValue(id)}"`).join(',');
            const actualsRows = await fetchRecords(
              CONFIG.apps.actuals,
              `worker_id in (${ulidInVals}) order by $id asc limit 500`,
              ['worker_id', 'assignment_id']
            ).catch(() => []);

            const ulidToAssignId = {};
            const assignIdsForLookup = [];
            actualsRows.forEach((record) => {
              const ulid = getFieldValue(record, 'worker_id').trim();
              const assignId = getFieldValue(record, 'assignment_id').trim();
              if (ulid && assignId && !ulidToAssignId[ulid]) {
                ulidToAssignId[ulid] = assignId;
                assignIdsForLookup.push(assignId);
              }
            });

            if (assignIdsForLookup.length > 0) {
              const uniqueAssignIds2 = Array.from(new Set(assignIdsForLookup));
              const assignInVals = uniqueAssignIds2.map((id) => `"${escapeKintoneQueryValue(id)}"`).join(',');
              const assignRows2 = await fetchRecords(
                CONFIG.apps.assignments,
                `assignment_id in (${assignInVals}) order by $id asc limit 500`,
                ['assignment_id', 'worker_id']
              ).catch(() => []);

              const assignToWrk2 = {};
              assignRows2.forEach((record) => {
                const assignId = getFieldValue(record, 'assignment_id').trim();
                const wrkId = getFieldValue(record, 'worker_id').trim();
                if (assignId && wrkId) assignToWrk2[assignId] = wrkId;
              });

              const wrkIds2 = Array.from(new Set(Object.values(assignToWrk2)));
              if (wrkIds2.length > 0) {
                const wrkInVals = wrkIds2.map((id) => `"${escapeKintoneQueryValue(id)}"`).join(',');
                const wrkRows2 = await fetchRecords(
                  CONFIG.apps.workers,
                  `worker_id in (${wrkInVals}) order by $id asc limit 500`,
                  ['worker_id', 'last_name', 'first_name']
                ).catch(() => []);

                const wrkToName2 = {};
                wrkRows2.forEach((record) => {
                  const wrkId = getFieldValue(record, 'worker_id').trim();
                  const lastName = getFieldValue(record, 'last_name').trim();
                  const firstName = getFieldValue(record, 'first_name').trim();
                  const name = `${lastName} ${firstName}`.trim();
                  if (wrkId && name) wrkToName2[wrkId] = name;
                });

                ulidUnresolved.forEach((ulid) => {
                  const assignId = ulidToAssignId[ulid];
                  const wrkId = assignId ? assignToWrk2[assignId] : '';
                  const name = wrkId ? wrkToName2[wrkId] : '';
                  if (name) {
                    optionMap.set(ulid, { name, isIntroducer: false, resolved: true });
                  }
                });
                console.log('[fetchWorkerOptionsByIds] assignment経由解決後 optionMap:', optionMap.size, '/', normalizedIds.length);
              }
            }
          }
        } catch (e) {
          console.warn('[fetchWorkerOptionsByIds] assignment経由ルックアップ失敗:', e);
        }
      }

      return normalizedIds.map((workerId) => {
        const row = optionMap.get(workerId);
        return {
          id: workerId,
          name: row ? row.name : workerId,
          isIntroducer: row ? row.isIntroducer : false,
          resolved: !!row
        };
      });
    }).catch(() => {
      return fetchAllWorkers().then((records) => {
        const map = new Map();
        (records || []).forEach((record) => {
          const workerId = getFieldValue(record, 'worker_id').trim();
          if (workerId) {
            map.set(workerId, {
              name: getWorkerDisplayName(record) || workerId,
              isIntroducer: normalizeViaDestination(getWorkerGroup(record)) === '紹介',
              resolved: true
            });
          }
        });
        return normalizedIds.map((workerId) => {
          const row = map.get(workerId);
          return {
            id: workerId,
            name: row ? row.name : workerId,
            isIntroducer: row ? row.isIntroducer : false,
            resolved: !!row
          };
        });
      });
    });
  }

  async function resolveWorkerDisplayNameByAnyId(workerIdentity) {
    const targetId = String(workerIdentity || '').trim();
    if (!targetId) {
      return '';
    }

    // ① DROP_DOWN optionsのラベルマップから直接名前を取得（最優先・最速）
    try {
      const { workerIdLabelMap, workerCode, workerType } = await resolveActualsFieldCodes();
      if (workerIdLabelMap && workerIdLabelMap[targetId]) {
        console.log('[resolveWorkerDisplayNameByAnyId] DROP_DOWN label →', targetId, '=', workerIdLabelMap[targetId]);
        return workerIdLabelMap[targetId];
      }

      // ② 実績アプリから worker_id で検索（DROP_DOWN型なので "in" を使う）
      const isDropDown = !workerType || /^(DROP_DOWN|RADIO_BUTTON|MULTI_SELECT|CHECK_BOX)$/i.test(workerType);
      const actualsQuery = isDropDown
        ? `${workerCode} in ("${escapeKintoneQueryValue(targetId)}") order by $id asc limit 1`
        : `${workerCode} = "${escapeKintoneQueryValue(targetId)}" order by $id asc limit 1`;
      const actualsRecords = await fetchRecords(CONFIG.apps.actuals, actualsQuery).catch(() => []);
      if (actualsRecords && actualsRecords.length > 0) {
        const rec = actualsRecords[0];
        // USER_SELECT型の作業者フィールドから名前を取得
        const sakusha = rec['作業者'];
        if (sakusha && Array.isArray(sakusha.value) && sakusha.value.length > 0) {
          const name = String(sakusha.value[0].name || '').trim();
          if (name) {
            console.log('[resolveWorkerDisplayNameByAnyId] 実績.作業者 →', targetId, '=', name);
            return name;
          }
        }
        // それ以外の全USER_SELECTフィールドも試す
        for (const code of Object.keys(rec || {})) {
          const f = rec[code];
          if (!f || !Array.isArray(f.value) || !f.value.length) continue;
          const names = f.value.map((u) => String(u && u.name ? u.name : '')).filter(Boolean);
          if (names.length) {
            console.log('[resolveWorkerDisplayNameByAnyId] 実績フィールド', code, '→', targetId, '=', names[0]);
            return names[0];
          }
        }
      }
    } catch (e) { /* 実績アプリ検索失敗時はApp165に fallback */ }

    const findByField = async (fieldCode) => {
      if (!fieldCode) {
        return '';
      }
      // テキスト型フィールドに "in" は使えないため "=" で検索する
      const query = `${fieldCode} = "${escapeKintoneQueryValue(targetId)}" order by $id asc limit 1`;
      const records = await fetchRecords(CONFIG.apps.workers, query).catch(() => []);
      const found = records && records.length ? records[0] : null;
      return getWorkerDisplayName(found).trim();
    };

    try {
      await resolveWorkerFieldCodes();
      const candidateCodes = (WORKER_FIELD_CODES_CACHE && Array.isArray(WORKER_FIELD_CODES_CACHE.idCandidateCodes))
        ? WORKER_FIELD_CODES_CACHE.idCandidateCodes
        : ['worker_id', 'id', 'worker_ulid', 'worker_uuid', 'worker_key'];
      for (let i = 0; i < candidateCodes.length; i += 1) {
        const code = candidateCodes[i];
        if (!code) {
          continue;
        }
        const byCodeName = await findByField(code);
        if (byCodeName) {
          return byCodeName;
        }
      }

      if (/^\d+$/.test(targetId)) {
        const byRecordNo = await fetchRecords(CONFIG.apps.workers, `$id = ${String(Number(targetId))} order by $id asc limit 1`);
        const foundByRecordNo = byRecordNo && byRecordNo.length ? byRecordNo[0] : null;
        const nameByRecordNo = getWorkerDisplayName(foundByRecordNo).trim();
        if (nameByRecordNo) {
          return nameByRecordNo;
        }
      }
    } catch (e) {
    }

    const all = WORKERS_ALL_CACHE || WORKERS_CACHE || [];
    const foundByCache = findWorkerRecordByIdentity(all || [], targetId);
    if (foundByCache) {
      const name = getWorkerDisplayName(foundByCache).trim();
      if (name) {
        return name;
      }
    }

    try {
      const workersForScan = await fetchAllWorkers();
      const foundByScan = findWorkerRecordByIdentity(workersForScan, targetId);
      const nameByScan = getWorkerDisplayName(foundByScan).trim();
      if (nameByScan) {
        return nameByScan;
      }
    } catch (e) {
    }

    return '';
  }

  async function fetchIntroducerOptionsByPeriod(year, month) {
    const workerIds = await fetchActualWorkerIdsByPeriod(year, month);
    if (!workerIds.length) {
      return [];
    }
    const workerSet = new Set(workerIds.map((id) => String(id || '').trim()).filter(Boolean));
    const workers = await fetchAllWorkers();
    const suppliers = await fetchSuppliers();
    const supplierById = new Map();
    (suppliers || []).forEach((supplier) => {
      const id = getFieldValue(supplier, 'supplier_id').trim() || getFieldValue(supplier, 'corporate_worker_id').trim();
      const name = getFieldValue(supplier, 'company_name').trim();
      if (id) {
        supplierById.set(id, name || id);
      }
    });

    const optionMap = new Map();
    (workers || []).forEach((record) => {
      const workerId = getFieldValue(record, 'worker_id').trim();
      if (!workerId || !workerSet.has(workerId)) {
        return;
      }
      const via = normalizeViaDestination(getWorkerGroup(record));
      if (via !== '紹介') {
        return;
      }
      const introducerId = String(getWorkerIntroducer(record) || '').trim();
      if (!introducerId) {
        return;
      }
      const introducerName = supplierById.get(introducerId) || introducerId;
      optionMap.set(introducerId, introducerName);
    });

    return Array.from(optionMap.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => String(a.name || a.id).localeCompare(String(b.name || b.id), 'ja'));
  }

  function openBillingIssueModal() {
    // 支払明細モーダルを開くたびに稼働者キャッシュをクリアして最新データを取得する
    // （別タブ等でkintoneの稼働者マスタを修正した場合にも必ず反映されるようにする）
    WORKERS_ALL_CACHE = null;
    WORKERS_CACHE = null;
    WORKER_FIELD_CODES_CACHE = null;
    ACTUAL_WORKER_IDS_BY_PERIOD_CACHE = {};
    ACTUAL_WORKER_NAMES_BY_PERIOD_CACHE = {};

    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;

    const fields = {
      document_target: {
        label: '1. 発行対象',
        type: 'select',
        required: true,
        options: ['', '見積もり/請求書：クライアント（依頼者）', '支払明細書：稼働者', '支払明細書：紹介者', '支払明細書：VANZAI職員']
      },
      client_document_type: {
        label: '2. 帳票の種別',
        type: 'select',
        options: ['', '請求書', '見積書'],
        defaultValue: '請求書'
      },
      client_company: {
        label: '3. クライアント会社',
        type: 'select',
        options: ['']
      },
      issue_year: { label: '4. 年', type: 'number', required: true, defaultValue: String(year), layout: 'half' },
      issue_month: { label: '4. 月', type: 'number', required: true, defaultValue: String(month), layout: 'half' },
      responsible_name: {
        label: '5. クライアント責任者',
        type: 'select',
        options: ['']
      },
      subject_manual: {
        label: '6. 件名（手入力）',
        type: 'text',
        defaultValue: `${year}年${month}月分_`
      },
      fixed_office_fee: {
        label: '6. 固定事務局費（手入力）',
        type: 'number'
      },
      payout_worker: {
        label: '5. 対象者',
        type: 'select',
        options: ['']
      },
      staff_support_fee: {
        label: '6. 職員 運営協力費（手入力）',
        type: 'number',
        defaultValue: '0'
      },
      payout_output_mode: {
        label: '7. 出力方法',
        type: 'select',
        options: ['', '単票（選択稼働者のみ）', '一括ZIP（当月出勤者全員）'],
        defaultValue: '単票（選択稼働者のみ）'
      }
    };

    const overlay = buildModal('見積/請求書、支払明細書の発行', fields, async (inputs, modal) => {
      const submitButton = modal.querySelector('.kintoneplugin-button-dialog-ok');
      const target = inputs.document_target.value;
      const yearValue = Number(inputs.issue_year.value);
      const monthValue = Number(inputs.issue_month.value);

      if (!target) {
        alert('発行対象を選択してください');
        return;
      }
      if (!Number.isFinite(yearValue) || yearValue < 2000 || yearValue > 2100) {
        alert('年を正しく入力してください（2000〜2100）');
        return;
      }
      if (!Number.isFinite(monthValue) || monthValue < 1 || monthValue > 12) {
        alert('月を正しく入力してください（1〜12）');
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = '処理中...';

      try {
        const periodKey = toPeriodKey(yearValue, monthValue);

        if (target === '見積もり/請求書：クライアント（依頼者）') {
          const documentType = inputs.client_document_type.value;
          const clientCompany = String(inputs.client_company.value || '').trim();
          const responsible = inputs.responsible_name.value;
          const subject = String(inputs.subject_manual.value || '').trim();
          const fixedOfficeFeeRaw = String(inputs.fixed_office_fee.value || '').trim();
          const hasFixedOfficeFee = fixedOfficeFeeRaw !== '';
          const fixedOfficeFeeAmount = hasFixedOfficeFee ? parseAmountNumber(fixedOfficeFeeRaw) : 0;

          if (!documentType) {
            throw new Error('クライアント帳票種別（請求書/見積書）を選択してください');
          }
          if (!clientCompany) {
            throw new Error('クライアント会社を選択してください');
          }
          if (!responsible) {
            throw new Error('クライアント責任者を選択してください');
          }
          if (!subject) {
            throw new Error('件名を入力してください');
          }
          if (hasFixedOfficeFee && (!Number.isFinite(fixedOfficeFeeAmount) || fixedOfficeFeeAmount < 0)) {
            throw new Error('固定事務局費は0以上の数値で入力してください');
          }

          const invoiceFields = await resolveInvoiceFieldCodes();
          const { baseQuery, typedRecords, created, createdRecordId } = await ensureInvoiceRecordExists(
            invoiceFields,
            periodKey,
            documentType,
            responsible,
            subject,
            fixedOfficeFeeAmount,
            hasFixedOfficeFee,
            { forceCreate: !invoiceFields.subjectCode, clientCompany }
          );

          if (!typedRecords.length) {
            throw new Error('見積書/請求書レコードの作成に失敗しました');
          }

          const query = baseQuery.replace('order by $id asc', 'order by $id desc');

          if (hasFixedOfficeFee) {
            if (!invoiceFields.fixedOfficeFeeCode) {
              throw new Error('請求書アプリに「固定事務局費」フィールドが見つかりません（候補: fixed_office_fee / office_fee / admin_fee）');
            }

            const targetRecords = typedRecords;

            if (!targetRecords.length) {
              throw new Error('固定事務局費を反映する請求書レコードが見つかりません。先に対象月の請求書を生成してください');
            }

            const updateRows = targetRecords
              .filter((record) => record.$id && record.$id.value)
              .map((record) => ({
                id: String(record.$id.value),
                record: {
                  [invoiceFields.fixedOfficeFeeCode]: { value: String(fixedOfficeFeeAmount) }
                }
              }));

            await updateRecordsInChunks(invoiceFields.appId, updateRows);
          }

          document.body.style.overflow = '';
          document.body.removeChild(modal);
          const latestRecord = pickLatestRecord(typedRecords);
          const latestRecordId = createdRecordId || getRecordIdValue(latestRecord);
          if (!latestRecordId) {
            openAppWithQuery(invoiceFields.appId, query);
            return;
          }

          const pdfResult = await generateAndAttachInvoicePdf(invoiceFields, latestRecordId, {
            periodKey,
            documentType,
            clientCompany,
            responsible,
            subject,
            fixedOfficeFeeAmount,
            hasFixedOfficeFee,
            registrationNumber: 'T2011201021906'
          });

          const storageLabel = pdfResult.storage === 'kintone'
            ? 'Kintone添付'
            : (pdfResult.storage === 'external' ? '外部ストレージ保存' : 'ローカル保存');
          const urlSavedLine = pdfResult.storage === 'external'
            ? `URL保存: ${pdfResult.urlSaved ? 'App171に保存済み' : '未保存（URLフィールド未設定）'}`
            : '';

          showStyledDialog(
            `${created ? '見積書/請求書を作成しました' : '既存レコードを表示します'}\n${periodKey} / ${documentType} / ${clientCompany} / ${responsible}\nPDF: ${pdfResult.fileName}\n保存先: ${storageLabel}${urlSavedLine ? `\n${urlSavedLine}` : ''}`,
            {
              kind: 'success',
              title: '処理結果',
              detailButtonLabel: '詳細確認',
              onDetail: () => openAppRecord(invoiceFields.appId, latestRecordId)
            }
          );
          return;
        }

        const payoutTargetId = String(inputs.payout_worker.value || '').trim();
        const selectedWorkerOption = payoutWorkerInput && payoutWorkerInput.options
          ? payoutWorkerInput.options[payoutWorkerInput.selectedIndex]
          : null;
        const selectedWorkerOptionText = selectedWorkerOption ? String(selectedWorkerOption.textContent || '').trim() : '';
        const selectedWorkerName = selectedWorkerOptionText && !selectedWorkerOptionText.startsWith('⚠')
          ? selectedWorkerOptionText
          : '';
        const supportFeeNum = parseAmountNumber(inputs.staff_support_fee ? inputs.staff_support_fee.value : 0);
        if (!payoutTargetId) {
          throw new Error('対象者を選択してください');
        }

        const payoutFields = await resolvePayoutFieldCodes();
        if (!payoutFields.attachmentCode) {
          throw new Error('支払明細アプリにPDF添付フィールドが見つかりません（FILEフィールドを設定してください）');
        }

        let ensureResult = null;
        let pdfResult = null;

        if (target === '支払明細書：稼働者') {
          ensureResult = await ensurePayoutRecordExists(payoutFields, periodKey, payoutTargetId, { supplierId: '' });
          pdfResult = await generateAndAttachPayoutPdf(payoutFields, ensureResult.recordId, {
            workerId: payoutTargetId,
            workerName: selectedWorkerName
          });
        } else if (target === '支払明細書：紹介者') {
          const suppliers = await fetchSuppliers();
          const supplierRecord = (suppliers || []).find((row) => {
            const id = getFieldValue(row, 'supplier_id').trim() || getFieldValue(row, 'corporate_worker_id').trim();
            return id === payoutTargetId;
          });
          const supplierName = supplierRecord ? (getFieldValue(supplierRecord, 'company_name').trim() || payoutTargetId) : payoutTargetId;
          const introducerDetail = await buildIntroducerPayoutDetail(periodKey, payoutTargetId, supplierName);
          if (!introducerDetail.lineItems.length) {
            throw new Error('紹介者に紐づく稼働実績が見つかりません');
          }
          ensureResult = await ensurePayoutRecordExists(payoutFields, periodKey, payoutTargetId, { supplierId: payoutTargetId });
          pdfResult = await generateAndAttachPayoutPdf(payoutFields, ensureResult.recordId, {
            workerId: payoutTargetId,
            workerName: supplierName,
            lineItems: introducerDetail.lineItems,
            summaryRows: introducerDetail.summaryRows,
            note: '紹介者向け支払明細'
          });
        } else if (target === '支払明細書：VANZAI職員') {
          const staffRecords = await fetchVanzaiStaffs();
          const staffRecord = (staffRecords || []).find((row) => getFieldValue(row, 'id').trim() === payoutTargetId);
          if (!staffRecord) {
            throw new Error('職員情報が見つかりません');
          }
          const staffName = getFieldValue(staffRecord, 'name').trim() || payoutTargetId;
          const staffRole = getFieldValue(staffRecord, 'role').trim();
          const staffDetail = await buildStaffPayoutDetail(periodKey, staffRecord, supportFeeNum);
          if (!staffDetail.lineItems.length) {
            throw new Error('対象職員向けの支払明細計算結果がありません');
          }
          ensureResult = await ensurePayoutRecordExists(payoutFields, periodKey, payoutTargetId, { supplierId: '' });
          const staffNote = staffRole.includes('プレイングマネージャー')
            ? `職員向け支払明細（運営協力費: ${supportFeeNum.toLocaleString('ja-JP')}円）`
            : '職員向け支払明細';
          pdfResult = await generateAndAttachPayoutPdf(payoutFields, ensureResult.recordId, {
            workerId: payoutTargetId,
            workerName: staffName,
            lineItems: staffDetail.lineItems,
            summaryRows: staffDetail.summaryRows,
            note: staffNote
          });
        } else {
          throw new Error('発行対象を選択してください');
        }

        document.body.style.overflow = '';
        document.body.removeChild(modal);

        const storageLabel = pdfResult.storage === 'kintone'
          ? 'Kintone添付'
          : (pdfResult.storage === 'external' ? '外部ストレージ保存' : 'ローカル保存');
        showStyledDialog(
          `${ensureResult.created ? '支払明細を作成しました' : '既存支払明細を更新しました'}\n${periodKey} / ${payoutTargetId}\nPDF: ${pdfResult.fileName}\n保存先: ${storageLabel}`,
          {
            kind: 'success',
            title: '処理結果',
            detailButtonLabel: '詳細確認',
            onDetail: () => {
              if (ensureResult.recordId) {
                openAppRecord(payoutFields.appId, ensureResult.recordId);
              }
            }
          }
        );
        return;
      } catch (err) {
        alert(err && err.message ? err.message : '出力処理に失敗しました');
      } finally {
        submitButton.disabled = false;
        submitButton.textContent = '確認へ移動';
      }
    });

    const submitButton = overlay.querySelector('.kintoneplugin-button-dialog-ok');
    if (submitButton) {
      submitButton.textContent = '確認へ移動';
    }

    const targetInput = overlay.querySelector('[data-code="document_target"]');
    const yearInput = overlay.querySelector('[data-code="issue_year"]');
    const monthInput = overlay.querySelector('[data-code="issue_month"]');
    const clientTypeInput = overlay.querySelector('[data-code="client_document_type"]');
    const clientCompanyInput = overlay.querySelector('[data-code="client_company"]');
    const responsibleInput = overlay.querySelector('[data-code="responsible_name"]');
    const subjectInput = overlay.querySelector('[data-code="subject_manual"]');
    const fixedOfficeFeeInput = overlay.querySelector('[data-code="fixed_office_fee"]');
    const payoutWorkerInput = overlay.querySelector('[data-code="payout_worker"]');
    const staffSupportFeeInput = overlay.querySelector('[data-code="staff_support_fee"]');
    const payoutOutputInput = overlay.querySelector('[data-code="payout_output_mode"]');

    const rowClientType = overlay.querySelector('[data-field-code="client_document_type"]');
    const rowClientCompany = overlay.querySelector('[data-field-code="client_company"]');
    const rowResponsible = overlay.querySelector('[data-field-code="responsible_name"]');
    const rowSubject = overlay.querySelector('[data-field-code="subject_manual"]');
    const rowFixedOfficeFee = overlay.querySelector('[data-field-code="fixed_office_fee"]');
    const rowPayoutWorker = overlay.querySelector('[data-field-code="payout_worker"]');
    const rowStaffSupportFee = overlay.querySelector('[data-field-code="staff_support_fee"]');
    const rowPayoutOutput = overlay.querySelector('[data-field-code="payout_output_mode"]');

    const syncSubject = () => {
      const y = Number(yearInput.value);
      const m = Number(monthInput.value);
      if (!Number.isFinite(y) || !Number.isFinite(m) || m < 1 || m > 12) {
        return;
      }
      const pattern = /^\d{4}年\d{1,2}月分_/;
      if (!subjectInput.value || pattern.test(subjectInput.value)) {
        subjectInput.value = `${y}年${m}月分_`;
      }
    };

    const refreshWorkerOptions = () => {
      const y = Number(yearInput.value);
      const m = Number(monthInput.value);
      const target = targetInput.value;
      const isWorkerTarget = target === '支払明細書：稼働者';
      const isIntroducerTarget = target === '支払明細書：紹介者';
      const isStaffTarget = target === '支払明細書：VANZAI職員';
      payoutWorkerInput.innerHTML = '';
      const loadingOption = document.createElement('option');
      loadingOption.value = '';
      loadingOption.textContent = '読み込み中...';
      payoutWorkerInput.appendChild(loadingOption);
      payoutWorkerInput.disabled = true;

      if (!Number.isFinite(y) || !Number.isFinite(m) || m < 1 || m > 12) {
        const invalidOption = document.createElement('option');
        invalidOption.value = '';
        invalidOption.textContent = '年月を正しく入力してください';
        payoutWorkerInput.innerHTML = '';
        payoutWorkerInput.appendChild(invalidOption);
        return;
      }

      const renderNoData = (message) => {
        payoutWorkerInput.innerHTML = '';
        const empty = document.createElement('option');
        empty.value = '';
        empty.textContent = message;
        payoutWorkerInput.appendChild(empty);
        payoutWorkerInput.disabled = true;
      };

      const renderOptions = (rows) => {
        payoutWorkerInput.innerHTML = '';
        const empty = document.createElement('option');
        empty.value = '';
        empty.textContent = rows.length ? `選択してください（${rows.length}件）` : '該当データなし';
        payoutWorkerInput.appendChild(empty);
        rows.forEach((row, idx) => {
          const option = document.createElement('option');
          option.value = row.id;
          const displayText = row && row.name ? String(row.name).trim() : '';
          option.textContent = displayText || `⚠ 名前未設定（候補${idx + 1}）`;
          payoutWorkerInput.appendChild(option);
        });
        payoutWorkerInput.disabled = rows.length === 0;
      };

      (isWorkerTarget
        ? fetchActualWorkerIdsByPeriod(y, m)
          .then((workerIds) => Promise.all([
            fetchWorkerOptionsByIds(workerIds),
            fetchActualWorkerNamesByPeriod(y, m)
          ]).then(([workers, actualNameMap]) => ({ kind: 'worker', workerIds, workers, actualNameMap })))
        : (isIntroducerTarget
          ? fetchIntroducerOptionsByPeriod(y, m).then((rows) => ({ kind: 'introducer', rows }))
          : fetchVanzaiStaffs().then((rows) => ({ kind: 'staff', rows: (rows || []).map((record) => ({ id: getFieldValue(record, 'id').trim(), name: getFieldValue(record, 'name').trim() || getFieldValue(record, 'id').trim() })).filter((row) => row.id) }))))
        .then((payload) => {
          if (payload.kind === 'worker') {
            const workers = payload.workers || [];
            const workerIds = payload.workerIds || [];
            const actualNameMap = payload.actualNameMap || {};
            if (!workerIds.length || !workers.length) {
              renderNoData('該当月の出勤履歴なし');
              return;
            }
            const baseRows = workers.map((worker) => {
              const isResolved = !!(worker && worker.resolved);
              const actualName = String(actualNameMap[String(worker.id || '').trim()] || '').trim();
              const id = String((worker && worker.id) || '').trim();
              // isResolved=true でも name が空の場合は actualName にフォールバック
              const name = (isResolved && String(worker.name || '').trim())
                ? String(worker.name || '').trim()
                : actualName;
              console.log('[baseRows]', id, '→ resolved:', isResolved, 'name:', String(worker.name||''), 'actualName:', actualName, '採用:', name);
              return {
                id,
                name,
                isDummy: !isResolved
              };
            });

            Promise.all(baseRows.map(async (row) => {
              if (!row || !row.id || row.name) {
                return row;
              }
              const resolvedName = await resolveWorkerDisplayNameByAnyId(row.id);
              return {
                ...row,
                name: String(resolvedName || '').trim()
              };
            })).then((resolvedRows) => {
              renderOptions(resolvedRows.map((row) => ({
                ...row,
                name: row.name || `⚠ 名前未設定（ID:${row.id}）`
              })));
            }).catch(() => {
              renderOptions(baseRows.map((row) => ({
                ...row,
                name: row.name || `⚠ 名前未設定（ID:${row.id}）`
              })));
            });
            return;
          }
          if (payload.kind === 'introducer') {
            const rows = payload.rows || [];
            if (!rows.length) {
              renderNoData('該当月の紹介者データなし');
              return;
            }
            renderOptions(rows);
            return;
          }
          const rows = payload.rows || [];
          if (!rows.length) {
            renderNoData('職員データなし');
            return;
          }
          renderOptions(rows);
        })
        .catch(() => {
          payoutWorkerInput.innerHTML = '';
          const errorOption = document.createElement('option');
          errorOption.value = '';
          errorOption.textContent = '対象者の取得に失敗しました';
          payoutWorkerInput.appendChild(errorOption);
          payoutWorkerInput.disabled = true;
        });
    };

    const refreshVisibility = () => {
      const isClient = targetInput.value === '見積もり/請求書：クライアント（依頼者）';
      const isStaffTarget = targetInput.value === '支払明細書：VANZAI職員';
      rowClientType.style.display = isClient ? '' : 'none';
      rowClientCompany.style.display = isClient ? '' : 'none';
      rowResponsible.style.display = isClient ? '' : 'none';
      rowSubject.style.display = isClient ? '' : 'none';
      rowFixedOfficeFee.style.display = isClient ? '' : 'none';

      rowPayoutWorker.style.display = isClient ? 'none' : '';
      rowStaffSupportFee.style.display = (!isClient && isStaffTarget) ? '' : 'none';
      rowPayoutOutput.style.display = 'none';

      if (!isClient && fixedOfficeFeeInput) {
        fixedOfficeFeeInput.value = '';
      }
      if (!isClient && clientCompanyInput) {
        clientCompanyInput.value = '';
      }
      if (!isStaffTarget && staffSupportFeeInput) {
        staffSupportFeeInput.value = '0';
      }
    };

    const getClientCompanyFromRecord = (record) => {
      return getFieldValue(record, 'client_company').trim()
        || getFieldValue(record, 'cliant_company').trim()
        || getFieldValue(record, 'client_name').trim()
        || getFieldValue(record, 'company_name').trim();
    };

    const createEmptySelectOption = (text) => {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = text;
      return option;
    };

    Promise.all([fetchClients(), fetchStaffManagers(), fetchAssignmentList()]).then(([clients, staffManagers, assignments]) => {
      const companySet = new Set();
      const namesByCompany = new Map();
      const allResponsibleNames = new Set();

      const pushResponsible = (company, name) => {
        const normalizedCompany = String(company || '').trim();
        const normalizedName = String(name || '').trim();
        if (!normalizedName) {
          return;
        }
        allResponsibleNames.add(normalizedName);
        if (!normalizedCompany) {
          return;
        }
        if (!namesByCompany.has(normalizedCompany)) {
          namesByCompany.set(normalizedCompany, new Set());
        }
        namesByCompany.get(normalizedCompany).add(normalizedName);
      };

      (clients || []).forEach((record) => {
        const company = getClientCompanyFromRecord(record);
        if (company) {
          companySet.add(company);
        }
      });

      (staffManagers || []).forEach((record) => {
        const company = getClientCompanyFromRecord(record);
        const name = getFieldValue(record, 'name').trim();
        if (company) {
          companySet.add(company);
        }
        pushResponsible(company, name);
      });

      (assignments || []).forEach((record) => {
        const company = getFieldValue(record, 'company_name').trim();
        const owner = getFieldValue(record, 'owner_name').trim();
        if (company) {
          companySet.add(company);
        }
        pushResponsible(company, owner);
      });

      const companies = Array.from(companySet).sort((a, b) => a.localeCompare(b, 'ja'));
      const renderResponsibleOptions = () => {
        const selectedCompany = String(clientCompanyInput.value || '').trim();
        const names = selectedCompany && namesByCompany.has(selectedCompany)
          ? Array.from(namesByCompany.get(selectedCompany)).sort((a, b) => a.localeCompare(b, 'ja'))
          : Array.from(allResponsibleNames).sort((a, b) => a.localeCompare(b, 'ja'));
        const previousValue = String(responsibleInput.value || '').trim();

        responsibleInput.innerHTML = '';
        responsibleInput.appendChild(createEmptySelectOption(names.length ? '選択してください' : '候補なし'));
        names.forEach((name) => {
          const option = document.createElement('option');
          option.value = name;
          option.textContent = name;
          responsibleInput.appendChild(option);
        });

        if (previousValue && names.includes(previousValue)) {
          responsibleInput.value = previousValue;
        }
      };

      clientCompanyInput.innerHTML = '';
      clientCompanyInput.appendChild(createEmptySelectOption(companies.length ? '選択してください' : 'クライアント候補なし'));
      companies.forEach((company) => {
        const option = document.createElement('option');
        option.value = company;
        option.textContent = company;
        clientCompanyInput.appendChild(option);
      });

      clientCompanyInput.addEventListener('change', () => {
        responsibleInput.value = '';
        renderResponsibleOptions();
      });

      renderResponsibleOptions();
    }).catch(() => {
      clientCompanyInput.innerHTML = '';
      clientCompanyInput.appendChild(createEmptySelectOption('クライアント候補の取得に失敗しました'));

      responsibleInput.innerHTML = '';
      responsibleInput.appendChild(createEmptySelectOption('責任者候補の取得に失敗しました'));
    });

    targetInput.addEventListener('change', refreshVisibility);
    targetInput.addEventListener('change', refreshWorkerOptions);
    yearInput.addEventListener('input', () => {
      syncSubject();
      refreshWorkerOptions();
    });
    monthInput.addEventListener('input', () => {
      syncSubject();
      refreshWorkerOptions();
    });
    payoutOutputInput.value = '単票（選択稼働者のみ）';

    refreshVisibility();
    syncSubject();
    refreshWorkerOptions();

    document.body.style.overflow = 'hidden';
    document.body.appendChild(overlay);
  }

  function openAssignmentStaffingModal(selectedRecordId) {
    const staffingCodes = CONFIG.project_assignments.staffingFieldCodes;
    const fields = {
      record_picker: { label: '案件', type: 'select', required: true, options: [''] },
      assignment_detail: { label: '案件詳細', type: 'display' },
      company_name: { label: '会社名' },
      owner_name: { label: 'クライアント責任者', type: 'select', options: [''] },
      main_staff: { label: 'クライアント担当者', type: 'select', options: [''] },
      playing_manager: { label: 'プレイングマネージャー', type: 'select', required: true, options: [''] },
      director: { label: 'ディレクター', type: 'text', hidden: true },
      assistant_director: { label: 'アシスタントディレクター', type: 'select', options: [''] },
      field_staff: { label: 'スタッフ', type: 'text', hidden: true },
      headcount_required: { label: '必要人数', type: 'number' },
      headcount_director: { label: '人数内訳:ディレクター', type: 'number', layout: 'half' },
      headcount_staff: { label: '人数内訳:スタッフ', type: 'number', layout: 'half' },
      incentive: { label: 'インセンティブ', type: 'select', options: ['', '1件毎/+¥〇〇円', '¥1,000～¥6,000'] }
    };

    const overlay = buildModal('案件の人員調整', fields, (inputs, modal) => {
      const recordId = inputs.record_picker.value;
      if (!recordId) {
        alert('案件を選択してください');
        return;
      }

      if (!inputs.playing_manager || !inputs.playing_manager.value) {
        alert('プレイングマネージャーを選択してください');
        return;
      }

      const splitIds = (raw) => String(raw || '').split(/[、,\s]+/).map((v) => v.trim()).filter(Boolean);
      const directorLimit = Math.max(Number(inputs.headcount_director ? inputs.headcount_director.value : 0) || 0, 0);
      const staffLimit = Math.max(Number(inputs.headcount_staff ? inputs.headcount_staff.value : 0) || 0, 0);
      const selectedDirectorCount = splitIds(inputs.director ? inputs.director.value : '').length;
      const selectedStaffCount = splitIds(inputs.field_staff ? inputs.field_staff.value : '').length;
      if (selectedDirectorCount !== directorLimit) {
        alert(`ディレクターは${directorLimit}名選択してください（現在 ${selectedDirectorCount}名）`);
        return;
      }
      if (selectedStaffCount !== staffLimit) {
        alert(`スタッフは${staffLimit}名選択してください（現在 ${selectedStaffCount}名）`);
        return;
      }

      const record = {};
      const map = {
        company_name: staffingCodes.company_name,
        owner_name: staffingCodes.owner_name,
        main_staff: staffingCodes.main_staff,
        playing_manager: staffingCodes.playing_manager,
        director: staffingCodes.director,
        assistant_director: staffingCodes.assistant_director,
        field_staff: staffingCodes.field_staff,
        headcount_required: staffingCodes.headcount_required,
        headcount_director: staffingCodes.headcount_director,
        headcount_staff: staffingCodes.headcount_staff,
        incentive: staffingCodes.incentive
      };

      Object.keys(map).forEach((key) => {
        const input = inputs[key];
        if (!input) {
          return;
        }
        const value = input.value;
        record[map[key]] = { value: value || '' };
      });

      kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/record.json`, 'PUT', {
        app: CONFIG.apps.project_assignments,
        id: recordId,
        record
      }).then(() => {
        showToast('更新しました');
        document.body.style.overflow = '';
        document.body.removeChild(modal);
        ASSIGNMENT_LIST_CACHE = null;
      }).catch((err) => {
        alert('更新に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
      });
    });

    const recordSelect = overlay.querySelector('[data-code="record_picker"]');
    const detailInput = overlay.querySelector('[data-code="assignment_detail"]');
    const ownerSelect = overlay.querySelector('[data-code="owner_name"]');
    const mainStaffSelect = overlay.querySelector('[data-code="main_staff"]');
    const playingManagerSelect = overlay.querySelector('[data-code="playing_manager"]');
    const directorInput = overlay.querySelector('[data-code="director"]');
    const assistantDirectorSelect = overlay.querySelector('[data-code="assistant_director"]');
    const fieldStaffInput = overlay.querySelector('[data-code="field_staff"]');
    const headcountRequiredInput = overlay.querySelector('[data-code="headcount_required"]');
    const headcountDirectorInput = overlay.querySelector('[data-code="headcount_director"]');
    const headcountStaffInput = overlay.querySelector('[data-code="headcount_staff"]');

    const ownerRow = overlay.querySelector('.vanzai-form-row[data-field-code="owner_name"]');
    const mainStaffRow = overlay.querySelector('.vanzai-form-row[data-field-code="main_staff"]');
    const requiredRow = overlay.querySelector('.vanzai-form-row[data-field-code="headcount_required"]');
    const directorCountRow = overlay.querySelector('.vanzai-form-row[data-field-code="headcount_director"]');
    const staffCountRow = overlay.querySelector('.vanzai-form-row[data-field-code="headcount_staff"]');

    const createEditLockButton = (onToggle) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = '変更';
      button.style.cssText = 'padding:6px 12px;border:1px solid #d1d5db;border-radius:6px;background:#fff;color:#374151;cursor:pointer;font-size:12px;font-weight:600;';
      let editing = false;
      button.addEventListener('click', () => {
        editing = !editing;
        button.textContent = editing ? '確定' : '変更';
        button.style.background = editing ? '#2563eb' : '#fff';
        button.style.color = editing ? '#fff' : '#374151';
        button.style.borderColor = editing ? '#2563eb' : '#d1d5db';
        onToggle(editing);
      });
      return button;
    };

    const setInputEditable = (input, editable) => {
      if (!input) {
        return;
      }
      input.disabled = !editable;
      if (!editable) {
        input.style.background = '#f3f4f6';
        input.style.color = '#6b7280';
        input.style.cursor = 'not-allowed';
      } else {
        input.style.background = '#fff';
        input.style.color = '#111827';
        input.style.cursor = 'text';
      }
    };

    const updateHeadcountStaffAuto = () => {
      if (!headcountStaffInput) {
        return;
      }
      const required = Math.max(Number(headcountRequiredInput && headcountRequiredInput.value ? headcountRequiredInput.value : 0) || 0, 0);
      const director = Math.max(Number(headcountDirectorInput && headcountDirectorInput.value ? headcountDirectorInput.value : 0) || 0, 0);
      const staff = Math.max(required - director, 0);
      headcountStaffInput.value = String(staff);
      dispatchInputEvents(headcountStaffInput);
    };

    const mountLockedSection = (title, mountBeforeRow, fieldDefs, toggleHandler) => {
      if (!mountBeforeRow || !mountBeforeRow.parentNode) {
        return null;
      }

      const section = document.createElement('div');
      section.className = 'vanzai-form-row';
      section.style.border = '1px solid #e5e7eb';
      section.style.borderRadius = '10px';
      section.style.padding = '10px 12px';
      section.style.background = '#f8fafc';

      const header = document.createElement('div');
      header.style.display = 'flex';
      header.style.justifyContent = 'space-between';
      header.style.alignItems = 'center';
      header.style.marginBottom = '8px';

      const heading = document.createElement('div');
      heading.textContent = title;
      heading.style.fontSize = '12px';
      heading.style.fontWeight = '700';
      heading.style.color = '#374151';
      header.appendChild(heading);

      const editButton = createEditLockButton(toggleHandler);
      header.appendChild(editButton);
      section.appendChild(header);

      const body = document.createElement('div');
      body.style.display = 'grid';
      body.style.gridTemplateColumns = fieldDefs.length >= 3 ? 'repeat(3,minmax(0,1fr))' : 'repeat(2,minmax(0,1fr))';
      body.style.gap = '8px';

      fieldDefs.forEach((field) => {
        const wrapper = document.createElement('div');
        const miniLabel = document.createElement('div');
        miniLabel.textContent = field.label;
        miniLabel.style.fontSize = '11px';
        miniLabel.style.color = '#6b7280';
        miniLabel.style.marginBottom = '4px';
        wrapper.appendChild(miniLabel);

        if (field.input) {
          field.input.style.margin = '0';
          wrapper.appendChild(field.input);
        }
        body.appendChild(wrapper);
      });

      section.appendChild(body);
      mountBeforeRow.parentNode.insertBefore(section, mountBeforeRow);
      return section;
    };

    if (ownerRow) {
      mountLockedSection('クライアント窓口', ownerRow, [
        { label: 'クライアント責任者', input: ownerSelect },
        { label: 'クライアント担当者', input: mainStaffSelect }
      ], (editing) => {
        setInputEditable(ownerSelect, editing);
        setInputEditable(mainStaffSelect, editing);
      });
      ownerRow.style.display = 'none';
    }
    if (mainStaffRow) {
      mainStaffRow.style.display = 'none';
    }

    if (requiredRow) {
      mountLockedSection('登録人数', ownerRow || requiredRow, [
        { label: '必要人数', input: headcountRequiredInput },
        { label: 'ディレクター数', input: headcountDirectorInput },
        { label: 'スタッフ数', input: headcountStaffInput }
      ], (editing) => {
        setInputEditable(headcountRequiredInput, editing);
        setInputEditable(headcountDirectorInput, editing);
        setInputEditable(headcountStaffInput, false);
      });
      requiredRow.style.display = 'none';
    }
    if (directorCountRow) {
      directorCountRow.style.display = 'none';
    }
    if (staffCountRow) {
      staffCountRow.style.display = 'none';
    }

    setInputEditable(ownerSelect, false);
    setInputEditable(mainStaffSelect, false);
    setInputEditable(headcountRequiredInput, false);
    setInputEditable(headcountDirectorInput, false);
    setInputEditable(headcountStaffInput, false);
    updateHeadcountStaffAuto();

    const setSelectValue = (select, value) => {
      if (!select) {
        return;
      }
      const exists = Array.from(select.options).some((opt) => opt.value === value);
      if (value && !exists) {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }
      select.value = value || '';
    };

    const populateStaffOptions = (select, staffRecords) => {
      if (!select) {
        return;
      }
      select.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '-- 選択してください --';
      select.appendChild(emptyOption);
      staffRecords.forEach((record) => {
        const name = record.name && record.name.value ? record.name.value : '';
        if (!name) {
          return;
        }
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        select.appendChild(option);
      });
    };

    const populateVanzaiStaffOptions = (select, staffRecords) => {
      if (!select) {
        return;
      }
      const current = select.value || '';
      select.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '-- 選択してください --';
      select.appendChild(emptyOption);
      staffRecords.forEach((record) => {
        const staffId = record.id && record.id.value ? String(record.id.value).trim() : '';
        const name = record.name && record.name.value ? String(record.name.value).trim() : '';
        if (!staffId) {
          return;
        }
        const option = document.createElement('option');
        option.value = staffId;
        option.textContent = name ? `${staffId} ${name}` : staffId;
        select.appendChild(option);
      });
      if (current) {
        setSelectValue(select, current);
      }
    };

    const createWorkerPicker = (title, hiddenInput, getLimit, mountAfterRow) => {
      if (!hiddenInput || !mountAfterRow || !mountAfterRow.parentNode) {
        return null;
      }

      const wrapper = document.createElement('div');
      wrapper.className = 'vanzai-form-row';
      wrapper.style.border = '1px solid #e5e7eb';
      wrapper.style.borderRadius = '10px';
      wrapper.style.padding = '10px 12px';
      wrapper.style.background = '#ffffff';

      const header = document.createElement('div');
      header.style.display = 'flex';
      header.style.justifyContent = 'space-between';
      header.style.alignItems = 'center';
      header.style.marginBottom = '8px';

      const heading = document.createElement('div');
      heading.textContent = title;
      heading.style.fontSize = '12px';
      heading.style.fontWeight = '700';
      heading.style.color = '#374151';
      header.appendChild(heading);

      const count = document.createElement('div');
      count.style.fontSize = '12px';
      count.style.fontWeight = '700';
      count.style.color = '#1d4ed8';
      count.textContent = '選択 0/0';
      header.appendChild(count);

      const panel = document.createElement('div');
      panel.style.display = 'flex';
      panel.style.flexWrap = 'wrap';
      panel.style.gap = '8px';
      panel.style.alignItems = 'stretch';

      wrapper.appendChild(header);
      wrapper.appendChild(panel);
      mountAfterRow.parentNode.insertBefore(wrapper, mountAfterRow.nextSibling);

      const selected = new Set();
      let allWorkers = [];

      const parseStored = (raw) => String(raw || '')
        .split(/[、,\s]+/)
        .map((v) => v.trim())
        .filter(Boolean);

      const syncHiddenInput = () => {
        const value = Array.from(selected).join(',');
        hiddenInput.value = value;
        dispatchInputEvents(hiddenInput);
      };

      const render = () => {
        const limit = Math.max(Number(getLimit()) || 0, 0);
        if (selected.size > limit) {
          const limited = Array.from(selected).slice(0, limit);
          selected.clear();
          limited.forEach((id) => selected.add(id));
          syncHiddenInput();
        }
        count.textContent = `選択 ${selected.size}/${limit}`;
        panel.innerHTML = '';
        allWorkers.forEach((record) => {
          const workerId = record.worker_id && record.worker_id.value ? String(record.worker_id.value).trim() : '';
          const name = getWorkerDisplayName(record);
          if (!workerId) {
            return;
          }
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.textContent = name ? `${workerId} ${name}` : workerId;
          chip.style.cssText = 'padding:6px 10px;border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#334155;font-size:12px;cursor:pointer;width:220px;min-height:34px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center;';

          const setSelectedStyle = (isSelected) => {
            chip.style.background = isSelected ? '#2563eb' : '#fff';
            chip.style.borderColor = isSelected ? '#2563eb' : '#cbd5e1';
            chip.style.color = isSelected ? '#fff' : '#334155';
          };
          setSelectedStyle(selected.has(workerId));

          chip.addEventListener('click', () => {
            if (selected.has(workerId)) {
              selected.delete(workerId);
            } else {
              if (limit <= 0) {
                alert('先に人数を設定してください');
                return;
              }
              if (selected.size >= limit) {
                alert(`${title}は${limit}名まで選択できます`);
                return;
              }
              selected.add(workerId);
            }
            setSelectedStyle(selected.has(workerId));
            syncHiddenInput();
            count.textContent = `選択 ${selected.size}/${limit}`;
          });

          panel.appendChild(chip);
        });
      };

      const refresh = (workers) => {
        allWorkers = sortWorkersByLastNameKana(workers);
        const availableIds = new Set(allWorkers.map((record) => {
          return record.worker_id && record.worker_id.value ? String(record.worker_id.value).trim() : '';
        }).filter(Boolean));
        selected.clear();
        parseStored(hiddenInput.value).forEach((id) => {
          if (availableIds.has(id)) {
            selected.add(id);
          }
        });
        const limit = Math.max(Number(getLimit()) || 0, 0);
        if (selected.size > limit) {
          const limited = Array.from(selected).slice(0, limit);
          selected.clear();
          limited.forEach((id) => selected.add(id));
          syncHiddenInput();
        }
        render();
      };

      return { refresh, render, selected, wrapper };
    };

    const assistantRow = overlay.querySelector('.vanzai-form-row[data-field-code="assistant_director"]');
    const directorHiddenRow = overlay.querySelector('.vanzai-form-row[data-field-code="director"]');
    const staffHiddenRow = overlay.querySelector('.vanzai-form-row[data-field-code="field_staff"]');
    const basePickerRow = assistantRow || directorHiddenRow || staffHiddenRow || (directorInput ? directorInput.closest('.vanzai-form-row') : null);
    const directorPicker = createWorkerPicker('ディレクター選択（クリックで選択/解除）', directorInput, () => headcountDirectorInput ? headcountDirectorInput.value : 0, basePickerRow);
    const staffPicker = createWorkerPicker('スタッフ選択（クリックで選択/解除）', fieldStaffInput, () => headcountStaffInput ? headcountStaffInput.value : 0, directorPicker && directorPicker.wrapper ? directorPicker.wrapper : basePickerRow);
    if (directorHiddenRow) {
      directorHiddenRow.style.display = 'none';
    }
    if (staffHiddenRow) {
      staffHiddenRow.style.display = 'none';
    }

    fetchStaffManagers().then((staffRecords) => {
      populateStaffOptions(ownerSelect, staffRecords);
      populateStaffOptions(mainStaffSelect, staffRecords);
    });

    fetchVanzaiStaffs().then((staffRecords) => {
      populateVanzaiStaffOptions(playingManagerSelect, staffRecords || []);
    });

    fetchWorkers().then((workerRecords) => {
      if (assistantDirectorSelect) {
        assistantDirectorSelect.innerHTML = '';
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = 'なし';
        assistantDirectorSelect.appendChild(emptyOption);
        workerRecords.forEach((record) => {
          const workerId = record.worker_id && record.worker_id.value ? String(record.worker_id.value) : '';
          const name = getWorkerDisplayName(record);
          if (!workerId) {
            return;
          }
          const option = document.createElement('option');
          option.value = workerId;
          option.textContent = name ? `${workerId} ${name}` : workerId;
          assistantDirectorSelect.appendChild(option);
        });
      }

      if (directorPicker) {
        directorPicker.refresh(workerRecords || []);
      }
      if (staffPicker) {
        staffPicker.refresh(workerRecords || []);
      }
    });

    const rerenderPickers = () => {
      if (directorPicker) {
        directorPicker.render();
      }
      if (staffPicker) {
        staffPicker.render();
      }
    };
    const onHeadcountBaseChanged = () => {
      updateHeadcountStaffAuto();
      rerenderPickers();
    };
    if (headcountRequiredInput) {
      headcountRequiredInput.addEventListener('input', onHeadcountBaseChanged);
      headcountRequiredInput.addEventListener('change', onHeadcountBaseChanged);
    }
    if (headcountDirectorInput) {
      headcountDirectorInput.addEventListener('input', onHeadcountBaseChanged);
      headcountDirectorInput.addEventListener('change', onHeadcountBaseChanged);
    }
    fetchAssignmentList().then((records) => {
      recordSelect.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '選択してください';
      recordSelect.appendChild(emptyOption);

      const recordMap = {};
      records.forEach((record) => {
        const recordId = record.$id.value;
        const idValue = record.assignment_id ? record.assignment_id.value : '';
        const titleValue = record.assignment_title ? record.assignment_title.value : '';
        const facilityValue = record.facility_name ? record.facility_name.value : '';
        const eventValue = record.event_name ? record.event_name.value : '';
        const dateValue = record.start_date ? record.start_date.value : '';
        const labelParts = [idValue, titleValue || [facilityValue, eventValue].filter(Boolean).join(' '), dateValue]
          .filter(Boolean);
        const label = labelParts.join(' / ');
        const option = document.createElement('option');
        option.value = recordId;
        option.textContent = label || recordId;
        recordSelect.appendChild(option);
        recordMap[recordId] = record;
      });

      recordSelect.addEventListener('change', () => {
        const selected = recordMap[recordSelect.value];
        if (!selected) {
          return;
        }
        const map = {
          company_name: staffingCodes.company_name,
          owner_name: staffingCodes.owner_name,
          main_staff: staffingCodes.main_staff,
          playing_manager: staffingCodes.playing_manager,
          director: staffingCodes.director,
          assistant_director: staffingCodes.assistant_director,
          field_staff: staffingCodes.field_staff,
          headcount_required: staffingCodes.headcount_required,
          headcount_director: staffingCodes.headcount_director,
          headcount_staff: staffingCodes.headcount_staff,
          incentive: staffingCodes.incentive
        };
        Object.keys(map).forEach((key) => {
          const input = overlay.querySelector(`[data-code="${key}"]`);
          const code = map[key];
          const value = selected[code] ? selected[code].value : '';
          if (input) {
            if (input.tagName === 'SELECT') {
              setSelectValue(input, value);
            } else {
              input.value = value || '';
            }
          }
        });

        updateHeadcountStaffAuto();

        if (directorPicker) {
          directorPicker.refresh(WORKERS_CACHE || []);
        }
        if (staffPicker) {
          staffPicker.refresh(WORKERS_CACHE || []);
        }

        if (detailInput) {
          const titleValue = selected.assignment_title ? selected.assignment_title.value : '';
          const facilityValue = selected.facility_name ? selected.facility_name.value : '';
          const eventValue = selected.event_name ? selected.event_name.value : '';
          const dateValue = selected.start_date ? selected.start_date.value : '';
          const majorValue = selected.category_major ? selected.category_major.value : '';
          const middleValue = selected.category_middle ? selected.category_middle.value : '';
          const minorValue = selected.category_minor ? selected.category_minor.value : '';
          const addressValue = selected.address ? selected.address.value : '';
          const timeValues = [
            selected.gathering_time ? selected.gathering_time.value : '',
            selected.start_time ? selected.start_time.value : '',
            selected.end_time ? selected.end_time.value : '',
            selected.dismissal_time ? selected.dismissal_time.value : ''
          ].filter(Boolean);

          const detailItems = [
            { key: '案件タイトル', value: titleValue },
            { key: '開催日', value: dateValue },
            { key: 'カテゴリ', value: [majorValue, middleValue, minorValue].filter(Boolean).join(' / ') },
            { key: '施設名', value: facilityValue },
            { key: 'イベント名', value: eventValue },
            { key: '住所', value: addressValue }
          ];

          if (timeValues.length > 0) {
            detailItems.push({ key: '時間', value: timeValues.join(' / ') });
          }

          const list = detailInput.querySelector('.vanzai-detail-list');
          if (list) {
            list.innerHTML = '';
            detailItems.filter((item) => item.value).forEach((item) => {
              const li = document.createElement('li');
              li.className = 'vanzai-detail-item';
              const key = document.createElement('div');
              key.className = 'vanzai-detail-key';
              key.textContent = item.key;
              const value = document.createElement('div');
              value.className = 'vanzai-detail-value';
              value.textContent = item.value;
              li.appendChild(key);
              li.appendChild(value);
              list.appendChild(li);
            });
          }
        }
      });

      if (selectedRecordId) {
        recordSelect.value = String(selectedRecordId);
        recordSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }).catch((err) => {
      console.error('案件一覧取得エラー:', err);
    });

    document.body.style.overflow = 'hidden';
    document.body.appendChild(overlay);
  }

  function openAssignmentListModal() {
    const overlay = document.createElement('div');
    overlay.className = 'vanzai-modal-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';

    const modal = document.createElement('div');
    modal.className = 'vanzai-modal';
    modal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);width:95%;max-width:1400px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column;';

    const header = document.createElement('div');
    header.style.cssText = 'padding:20px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;background:#4A90E2;color:white;';
    const title = document.createElement('h2');
    title.textContent = '案件一覧';
    title.style.cssText = 'margin:0;font-size:18px;font-weight:600;';
    header.appendChild(title);

    const filterButton = document.createElement('button');
    filterButton.textContent = ASSIGNMENT_LIST_FILTER === 'incomplete' ? '全案件を表示' : '未入力案件のみを表示';
    filterButton.style.cssText = 'padding:8px 16px;border:1px solid rgba(249,115,22,0.5);border-radius:6px;background:linear-gradient(135deg,#f97316,#ea580c);color:white;cursor:pointer;font-size:14px;font-weight:600;box-shadow:0 4px 10px rgba(249,115,22,0.3);transition:all 0.2s;';
    filterButton.onmouseenter = () => { filterButton.style.transform = 'translateY(-1px)'; filterButton.style.boxShadow = '0 6px 14px rgba(249,115,22,0.4)'; };
    filterButton.onmouseleave = () => { filterButton.style.transform = 'translateY(0)'; filterButton.style.boxShadow = '0 4px 10px rgba(249,115,22,0.3)'; };
    filterButton.onclick = () => {
      ASSIGNMENT_LIST_FILTER = ASSIGNMENT_LIST_FILTER === 'all' ? 'incomplete' : 'all';
      document.body.removeChild(overlay);
      openAssignmentListModal();
    };
    header.appendChild(filterButton);

    const actualsFilterButton = document.createElement('button');
    actualsFilterButton.textContent = ASSIGNMENT_LIST_ACTUALS_FILTER === 'missing' ? '実績未入力の絞り込み解除' : '実績未入力だけを絞る';
    actualsFilterButton.style.cssText = 'padding:8px 16px;border:1px solid rgba(16,185,129,0.5);border-radius:6px;background:linear-gradient(135deg,#10b981,#059669);color:white;cursor:pointer;font-size:14px;font-weight:600;box-shadow:0 4px 10px rgba(16,185,129,0.25);transition:all 0.2s;';
    actualsFilterButton.onmouseenter = () => { actualsFilterButton.style.transform = 'translateY(-1px)'; actualsFilterButton.style.boxShadow = '0 6px 14px rgba(16,185,129,0.35)'; };
    actualsFilterButton.onmouseleave = () => { actualsFilterButton.style.transform = 'translateY(0)'; actualsFilterButton.style.boxShadow = '0 4px 10px rgba(16,185,129,0.25)'; };
    actualsFilterButton.onclick = () => {
      ASSIGNMENT_LIST_ACTUALS_FILTER = ASSIGNMENT_LIST_ACTUALS_FILTER === 'all' ? 'missing' : 'all';
      document.body.removeChild(overlay);
      openAssignmentListModal();
    };
    header.appendChild(actualsFilterButton);

    const tableWrapper = document.createElement('div');
    tableWrapper.style.cssText = 'overflow:auto;flex:1;padding:20px;';

    const table = document.createElement('table');
    table.style.cssText = 'width:100%;border-collapse:collapse;font-size:13px;';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.style.cssText = 'background:linear-gradient(to right,#f3f4f6,#e5e7eb);';

    const columns = [
      { label: 'ID', field: 'assignment_id' },
      { label: 'クライアント名', field: 'company_name' },
      { label: 'クライアント責任者', field: 'owner_name' },
      { label: 'クライアント担当者', field: 'main_staff' },
      { label: '案件タイトル', field: 'assignment_title' },
      { label: '住所', field: 'address' },
      { label: '開始日', field: 'start_date' },
      { label: '1日稼働時間(h)', field: 'work_hours' },
      { label: '必要人数', field: 'headcount_required' },
      { label: 'ディレクター', field: 'headcount_director' },
      { label: 'スタッフ', field: 'headcount_staff' },
      { label: 'ベース報酬', field: 'base_reward' },
      { label: 'ベース報酬:ディレクター', field: 'base_reward_director' },
      { label: 'ベース報酬:アシスタント', field: 'base_reward_assistant_director' },
      { label: 'ベース報酬:スタッフ', field: 'base_reward_staff' },
      { label: 'インセンティブ', field: 'incentive' }
    ];

    columns.forEach((col) => {
      const th = document.createElement('th');
      th.textContent = col.label;
      th.dataset.field = col.field;
      th.style.cssText = 'padding:12px 8px;text-align:left;border-bottom:2px solid #d1d5db;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none;position:relative;';
      
      if (ASSIGNMENT_LIST_SORT.column === col.field) {
        const arrow = document.createElement('span');
        arrow.textContent = ASSIGNMENT_LIST_SORT.direction === 'asc' ? ' ↑' : ' ↓';
        arrow.style.color = '#3b82f6';
        th.appendChild(arrow);
      }
      
      th.onmouseenter = () => { th.style.background = '#dbeafe'; };
      th.onmouseleave = () => { th.style.background = ''; };
      th.onclick = () => {
        if (ASSIGNMENT_LIST_SORT.column === col.field) {
          ASSIGNMENT_LIST_SORT.direction = ASSIGNMENT_LIST_SORT.direction === 'asc' ? 'desc' : 'asc';
        } else {
          ASSIGNMENT_LIST_SORT.column = col.field;
          ASSIGNMENT_LIST_SORT.direction = 'asc';
        }
        document.body.removeChild(overlay);
        openAssignmentListModal();
      };
      
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    table.appendChild(tbody);
    tableWrapper.appendChild(table);

    const footer = document.createElement('div');
    footer.style.cssText = 'padding:16px 20px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:12px;';

    const closeButton = document.createElement('button');
    closeButton.textContent = '閉じる';
    closeButton.className = 'kintoneplugin-button-dialog-cancel';
    closeButton.style.cssText = 'padding:10px 24px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:14px;';
    closeButton.onclick = () => {
      document.body.style.overflow = '';
      document.body.removeChild(overlay);
    };
    footer.appendChild(closeButton);

    modal.appendChild(header);
    modal.appendChild(tableWrapper);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    Promise.all([fetchAssignmentList(), fetchActualAssignmentIds()]).then(([records, actualIds]) => {
      tbody.innerHTML = '';
      
      let filteredRecords = records;
      if (ASSIGNMENT_LIST_FILTER === 'incomplete') {
        filteredRecords = records.filter((record) => {
          const owner = record.owner_name && record.owner_name.value ? record.owner_name.value : '';
          const mainStaff = record.main_staff && record.main_staff.value ? record.main_staff.value : '';
          const headcount = record.headcount_required && record.headcount_required.value ? record.headcount_required.value : '';
          const playing = record.playing_manager && record.playing_manager.value ? record.playing_manager.value : '';
          const staff = record.field_staff && record.field_staff.value ? record.field_staff.value : '';
          return !owner || !mainStaff || !headcount || !playing || !staff;
        });
      }

      if (ASSIGNMENT_LIST_ACTUALS_FILTER === 'missing') {
        filteredRecords = filteredRecords.filter((record) => {
          const assignmentId = record.assignment_id && record.assignment_id.value ? String(record.assignment_id.value).trim() : '';
          if (!assignmentId) {
            return false;
          }
          return !actualIds.has(assignmentId);
        });
      }
      
      filteredRecords.sort((a, b) => {
        const fieldName = ASSIGNMENT_LIST_SORT.column;
        const aValue = a[fieldName] && a[fieldName].value ? a[fieldName].value : '';
        const bValue = b[fieldName] && b[fieldName].value ? b[fieldName].value : '';
        
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        const isNumeric = !isNaN(aNum) && !isNaN(bNum);
        
        let comparison = 0;
        if (isNumeric) {
          comparison = aNum - bNum;
        } else {
          comparison = String(aValue).localeCompare(String(bValue), 'ja');
        }
        
        return ASSIGNMENT_LIST_SORT.direction === 'asc' ? comparison : -comparison;
      });
      
      filteredRecords.forEach((record) => {
        const row = document.createElement('tr');
        row.style.cssText = 'border-bottom:1px solid #e5e7eb;cursor:pointer;';
        row.onmouseenter = () => { row.style.background = '#fef3c7'; };
        row.onmouseleave = () => { row.style.background = 'white'; };
        row.onclick = () => {
          document.body.style.overflow = '';
          document.body.removeChild(overlay);
          openAssignmentStaffingModal(record.$id.value);
        };

        const getValue = (fieldName) => {
          return record[fieldName] && record[fieldName].value ? record[fieldName].value : '';
        };

        const cells = [
          getValue('assignment_id'),
          getValue('company_name'),
          getValue('owner_name'),
          getValue('main_staff'),
          getValue('assignment_title'),
          getValue('address'),
          getValue('start_date'),
          getValue('work_hours'),
          getValue('headcount_required'),
          getValue('headcount_director'),
          getValue('headcount_staff'),
          getValue('base_reward'),
          getValue('base_reward_director'),
          getValue('base_reward_assistant_director'),
          getValue('base_reward_staff'),
          getValue('incentive')
        ];

        cells.forEach((cellValue) => {
          const td = document.createElement('td');
          td.textContent = cellValue;
          td.style.cssText = 'padding:10px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;';
          td.title = cellValue;
          row.appendChild(td);
        });

        tbody.appendChild(row);
      });
    }).catch((err) => {
      console.error('案件一覧取得エラー:', err);
      tbody.innerHTML = '<tr><td colspan="16" style="padding:20px;text-align:center;color:#ef4444;">データの取得に失敗しました</td></tr>';
    });

    document.body.style.overflow = 'hidden';
    document.body.appendChild(overlay);
  }

  function openWorkerListModal() {
    console.info('稼働者一覧モーダルを表示します', { filter: WORKER_LIST_FILTER });
    let workerRecords = [];
    let selectedViaDestination = '';
    let selectedIntroducer = '';
    const workerListSort = { column: 'worker_id', direction: 'asc' };
    const workerListColumns = [
      { key: 'worker_id', label: '稼働者ID', sortable: true },
      { key: 'name', label: '氏名', sortable: true },
      { key: 'last_name_kana', label: '姓(カナ)', sortable: true },
      { key: 'via_destination', label: '経由先', sortable: true },
      { key: 'introducer_supplier', label: '紹介者/下請け', sortable: true },
      { key: 'phone', label: '電話', sortable: false },
      { key: 'email', label: 'メール', sortable: false },
      { key: 'is_active', label: '有効・無効', sortable: false },
    ];
    const workerListHeaderCells = {};

    const getWorkerViaDestination = (record) => normalizeViaDestination(getWorkerGroup(record));
    const getWorkerIntroducerForList = (record) => {
      const via = getWorkerViaDestination(record);
      if (isDirectViaDestination(via)) {
        return '';
      }
      return String(getWorkerIntroducer(record) || '').trim();
    };
    const getWorkerLastNameKana = (record) => {
      return record && record.lastname_furigana && record.lastname_furigana.value
        ? String(record.lastname_furigana.value).trim()
        : '';
    };

    const getWorkerSortValue = (record, columnKey) => {
      const workerId = record.worker_id && record.worker_id.value ? String(record.worker_id.value) : '';
      const lastName = record.last_name && record.last_name.value ? String(record.last_name.value) : '';
      const firstName = record.first_name && record.first_name.value ? String(record.first_name.value) : '';
      const name = `${lastName} ${firstName}`.trim();
      switch (columnKey) {
      case 'worker_id':
        return workerId;
      case 'name':
        return name;
      case 'last_name_kana':
        return getWorkerLastNameKana(record);
      case 'via_destination':
        return getWorkerViaDestination(record);
      case 'introducer_supplier':
        return getWorkerIntroducerForList(record);
      case 'phone':
        return record.phone && record.phone.value ? String(record.phone.value) : '';
      case 'email':
        return record.email && record.email.value ? String(record.email.value) : '';
      case 'is_active':
        return record.is_active && record.is_active.value ? String(record.is_active.value) : '';
      default:
        return '';
      }
    };

    const sortWorkerRecords = (records) => {
      const sorted = (records || []).slice();
      const column = workerListSort.column;
      const direction = workerListSort.direction === 'desc' ? -1 : 1;
      sorted.sort((a, b) => {
        const av = String(getWorkerSortValue(a, column) || '');
        const bv = String(getWorkerSortValue(b, column) || '');
        return av.localeCompare(bv, 'ja', { numeric: true, sensitivity: 'base' }) * direction;
      });
      return sorted;
    };

    const updateWorkerHeaderSortIndicators = () => {
      Object.keys(workerListHeaderCells).forEach((key) => {
        const th = workerListHeaderCells[key];
        if (!th) {
          return;
        }
        const col = workerListColumns.find((item) => item.key === key);
        if (!col) {
          return;
        }
        if (!col.sortable) {
          th.textContent = col.label;
          return;
        }
        const marker = workerListSort.column === key
          ? (workerListSort.direction === 'asc' ? ' ▲' : ' ▼')
          : ' ▽';
        th.textContent = `${col.label}${marker}`;
      });
    };

    const buildViaOptions = (records) => {
      const exists = new Set();
      records.forEach((record) => {
        const via = getWorkerViaDestination(record);
        if (via) {
          exists.add(via);
        }
      });
      return ['下請け', '紹介', 'VANZAI直接'].filter((via) => exists.has(via));
    };

    const buildIntroducerOptions = (records) => {
      const exists = new Set();
      records.forEach((record) => {
        const introducer = getWorkerIntroducerForList(record);
        if (introducer) {
          exists.add(introducer);
        }
      });
      return Array.from(exists).sort((a, b) => a.localeCompare(b, 'ja'));
    };

    const applyWorkerFilters = (records) => {
      let target = records;
      if (WORKER_LIST_FILTER === 'active') {
        target = target.filter((r) => (r.is_active && String(r.is_active.value || '') === '有効'));
      }
      if (selectedViaDestination) {
        target = target.filter((r) => getWorkerViaDestination(r) === selectedViaDestination);
      }
      if (selectedIntroducer) {
        target = target.filter((r) => getWorkerIntroducerForList(r) === selectedIntroducer);
      }
      return target;
    };

    const overlay = document.createElement('div');
    overlay.className = 'vanzai-modal-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';

    const modal = document.createElement('div');
    modal.className = 'vanzai-modal';
    modal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);width:95%;max-width:1200px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column;';

    const header = document.createElement('div');
    header.style.cssText = 'padding:20px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;background:#4A90E2;color:white;';
    const title = document.createElement('h2');
    title.textContent = '稼働者一覧';
    title.style.cssText = 'margin:0;font-size:18px;font-weight:600;';
    header.appendChild(title);

    const activeFilterButton = document.createElement('button');
    activeFilterButton.textContent = WORKER_LIST_FILTER === 'active' ? '全件を表示' : '有効のみに切り替え';
    activeFilterButton.style.cssText = 'padding:8px 16px;border:1px solid rgba(16,185,129,0.5);border-radius:6px;background:linear-gradient(135deg,#10b981,#059669);color:white;cursor:pointer;font-size:14px;font-weight:600;box-shadow:0 4px 10px rgba(16,185,129,0.25);transition:all 0.2s;';
    activeFilterButton.onmouseenter = () => { activeFilterButton.style.transform = 'translateY(-1px)'; activeFilterButton.style.boxShadow = '0 6px 14px rgba(16,185,129,0.35)'; };
    activeFilterButton.onmouseleave = () => { activeFilterButton.style.transform = 'translateY(0)'; activeFilterButton.style.boxShadow = '0 4px 10px rgba(16,185,129,0.25)'; };
    activeFilterButton.onclick = () => {
      WORKER_LIST_FILTER = WORKER_LIST_FILTER === 'all' ? 'active' : 'all';
      activeFilterButton.textContent = WORKER_LIST_FILTER === 'active' ? '全件を表示' : '有効のみに切り替え';
      console.info('稼働者一覧フィルタを切り替えました', { filter: WORKER_LIST_FILTER });
      renderWorkerRows();
    };
    header.appendChild(activeFilterButton);

    const tableWrapper = document.createElement('div');
    tableWrapper.style.cssText = 'overflow:auto;flex:1;padding:20px;';

    const filterBar = document.createElement('div');
    filterBar.style.cssText = 'display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;margin-bottom:12px;padding:12px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;';

    const viaFilterWrap = document.createElement('div');
    viaFilterWrap.style.cssText = 'display:flex;flex-direction:column;min-width:220px;gap:6px;';
    const viaFilterLabel = document.createElement('label');
    viaFilterLabel.textContent = '経由先';
    viaFilterLabel.style.cssText = 'font-size:12px;color:#374151;font-weight:600;';
    const viaFilterSelect = document.createElement('select');
    viaFilterSelect.style.cssText = 'padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;background:white;';
    viaFilterWrap.appendChild(viaFilterLabel);
    viaFilterWrap.appendChild(viaFilterSelect);
    filterBar.appendChild(viaFilterWrap);

    const introducerFilterWrap = document.createElement('div');
    introducerFilterWrap.style.cssText = 'display:flex;flex-direction:column;min-width:280px;gap:6px;';
    const introducerFilterLabel = document.createElement('label');
    introducerFilterLabel.textContent = '紹介者/下請け';
    introducerFilterLabel.style.cssText = 'font-size:12px;color:#374151;font-weight:600;';
    const introducerFilterSelect = document.createElement('select');
    introducerFilterSelect.style.cssText = 'padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;background:white;';
    introducerFilterWrap.appendChild(introducerFilterLabel);
    introducerFilterWrap.appendChild(introducerFilterSelect);
    filterBar.appendChild(introducerFilterWrap);

    const clearFilterButton = document.createElement('button');
    clearFilterButton.textContent = '絞り込み解除';
    clearFilterButton.style.cssText = 'padding:8px 14px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:13px;color:#374151;';
    filterBar.appendChild(clearFilterButton);

    tableWrapper.appendChild(filterBar);

    const table = document.createElement('table');
    table.style.cssText = 'width:100%;border-collapse:collapse;font-size:13px;';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.style.cssText = 'background:linear-gradient(to right,#f3f4f6,#e5e7eb);';
    workerListColumns.forEach((column) => {
      const th = document.createElement('th');
      th.textContent = column.label;
      th.style.cssText = 'padding:12px 8px;text-align:left;border-bottom:2px solid #d1d5db;font-weight:600;white-space:nowrap;';
      if (column.sortable) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.onclick = () => {
          if (workerListSort.column === column.key) {
            workerListSort.direction = workerListSort.direction === 'asc' ? 'desc' : 'asc';
          } else {
            workerListSort.column = column.key;
            workerListSort.direction = 'asc';
          }
          updateWorkerHeaderSortIndicators();
          renderWorkerRows();
        };
      }
      workerListHeaderCells[column.key] = th;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    updateWorkerHeaderSortIndicators();

    const tbody = document.createElement('tbody');
    table.appendChild(tbody);
    tableWrapper.appendChild(table);

    const footer = document.createElement('div');
    footer.style.cssText = 'padding:16px 20px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:12px;';

    const closeButton = document.createElement('button');
    closeButton.textContent = '閉じる';
    closeButton.className = 'kintoneplugin-button-dialog-cancel';
    closeButton.style.cssText = 'padding:10px 24px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:14px;';
    closeButton.onclick = () => {
      document.body.style.overflow = '';
      document.body.removeChild(overlay);
    };
    footer.appendChild(closeButton);

    modal.appendChild(header);
    modal.appendChild(tableWrapper);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    function populateFilterSelect(selectEl, values, currentValue, defaultLabel) {
      selectEl.innerHTML = '';
      const defaultOpt = document.createElement('option');
      defaultOpt.value = '';
      defaultOpt.textContent = defaultLabel;
      selectEl.appendChild(defaultOpt);
      values.forEach((value) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        selectEl.appendChild(opt);
      });
      selectEl.value = values.includes(currentValue) ? currentValue : '';
    }

    function syncFilterOptions() {
      const viaOptions = buildViaOptions(workerRecords);
      const introducerOptions = buildIntroducerOptions(workerRecords);

      if (selectedViaDestination && !viaOptions.includes(selectedViaDestination)) {
        selectedViaDestination = '';
      }
      if (selectedIntroducer && !introducerOptions.includes(selectedIntroducer)) {
        selectedIntroducer = '';
      }

      populateFilterSelect(viaFilterSelect, viaOptions, selectedViaDestination, 'すべての経由先');
      populateFilterSelect(introducerFilterSelect, introducerOptions, selectedIntroducer, 'すべての紹介者/下請け');
    }

    function renderWorkerRows() {
      tbody.innerHTML = '';
      const target = applyWorkerFilters(workerRecords);
      const sortedTarget = sortWorkerRecords(target);

      if (!sortedTarget.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="padding:20px;text-align:center;color:#6b7280;">条件に一致する稼働者がいません</td></tr>';
        console.info('稼働者一覧を描画しました', {
          total: workerRecords.length,
          shown: 0,
          filter: WORKER_LIST_FILTER,
          via_destination: selectedViaDestination,
          introducer_supplier: selectedIntroducer,
        });
        return;
      }

      sortedTarget.forEach((record) => {
        const row = document.createElement('tr');
        row.style.cssText = 'border-bottom:1px solid #e5e7eb;cursor:pointer;';
        row.onmouseenter = () => { row.style.background = '#fef3c7'; };
        row.onmouseleave = () => { row.style.background = 'white'; };
        row.onclick = () => {
          const workerId = record.worker_id && record.worker_id.value ? String(record.worker_id.value) : '';
          console.info('稼働者一覧行をクリックしました', { worker_id: workerId });
          document.body.style.overflow = '';
          document.body.removeChild(overlay);
          openWorkerDetailModal(record);
        };

        const workerId = record.worker_id && record.worker_id.value ? String(record.worker_id.value) : '';
        const lastName = record.last_name && record.last_name.value ? String(record.last_name.value) : '';
        const firstName = record.first_name && record.first_name.value ? String(record.first_name.value) : '';
        const name = `${lastName} ${firstName}`.trim();
        const lastNameKana = getWorkerLastNameKana(record);
        const group = getWorkerViaDestination(record);
        const introducer = getWorkerIntroducerForList(record);
        const phone = record.phone && record.phone.value ? String(record.phone.value) : '';
        const email = record.email && record.email.value ? String(record.email.value) : '';
        const active = record.is_active && record.is_active.value ? String(record.is_active.value) : '';

        [workerId, name, lastNameKana, group, introducer, phone, email, active].forEach((cellValue) => {
          const td = document.createElement('td');
          td.textContent = cellValue;
          td.style.cssText = 'padding:10px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;';
          td.title = cellValue;
          row.appendChild(td);
        });

        tbody.appendChild(row);
      });

      console.info('稼働者一覧を描画しました', {
        total: workerRecords.length,
        shown: sortedTarget.length,
        filter: WORKER_LIST_FILTER,
        via_destination: selectedViaDestination,
        introducer_supplier: selectedIntroducer,
        sort_column: workerListSort.column,
        sort_direction: workerListSort.direction,
      });
    }

    viaFilterSelect.addEventListener('change', () => {
      selectedViaDestination = String(viaFilterSelect.value || '');
      renderWorkerRows();
    });

    introducerFilterSelect.addEventListener('change', () => {
      selectedIntroducer = String(introducerFilterSelect.value || '');
      renderWorkerRows();
    });

    clearFilterButton.onclick = () => {
      selectedViaDestination = '';
      selectedIntroducer = '';
      syncFilterOptions();
      renderWorkerRows();
    };

    function openWorkerDetailModal(record) {
      const detailOverlay = document.createElement('div');
      detailOverlay.className = 'vanzai-modal-overlay';
      detailOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10001;display:flex;align-items:center;justify-content:center;';

      const detailModal = document.createElement('div');
      detailModal.className = 'vanzai-modal';
      detailModal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);width:92%;max-width:760px;max-height:88vh;overflow:hidden;display:flex;flex-direction:column;';

      const detailHeader = document.createElement('div');
      detailHeader.style.cssText = 'padding:20px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;background:#4A90E2;color:white;';
      const detailTitle = document.createElement('h2');
      detailTitle.textContent = '稼働者詳細';
      detailTitle.style.cssText = 'margin:0;font-size:18px;font-weight:600;';
      detailHeader.appendChild(detailTitle);

      const detailHeaderActions = document.createElement('div');
      detailHeaderActions.style.cssText = 'display:flex;align-items:center;gap:8px;';

      const payoutCreateButton = document.createElement('button');
      payoutCreateButton.textContent = '支払明細の作成';
      payoutCreateButton.style.cssText = 'padding:8px 12px;border:1px solid #34d399;border-radius:6px;background:#10b981;color:white;cursor:pointer;font-size:13px;font-weight:600;';

      const payoutReferenceButton = document.createElement('button');
      payoutReferenceButton.textContent = '支払明細の参照';
      payoutReferenceButton.style.cssText = 'padding:8px 12px;border:1px solid #93c5fd;border-radius:6px;background:#2563eb;color:white;cursor:pointer;font-size:13px;font-weight:600;';

      detailHeaderActions.appendChild(payoutCreateButton);
      detailHeaderActions.appendChild(payoutReferenceButton);
      detailHeader.appendChild(detailHeaderActions);

      const detailBody = document.createElement('div');
      detailBody.style.cssText = 'padding:20px;overflow:auto;';

      const workerId = record.worker_id && record.worker_id.value ? String(record.worker_id.value) : '';
      const lastName = record.last_name && record.last_name.value ? String(record.last_name.value) : '';
      const firstName = record.first_name && record.first_name.value ? String(record.first_name.value) : '';
      const lastKana = record.lastname_furigana && record.lastname_furigana.value ? String(record.lastname_furigana.value) : '';
      const firstKana = record.firstname_furigana && record.firstname_furigana.value ? String(record.firstname_furigana.value) : '';
      const viaDestination = normalizeViaDestination(getWorkerGroup(record));
      const workerFieldCodes = WORKER_FIELD_CODES_CACHE || { viaCode: 'via_destination', introducerCode: 'introducer_supplier' };
      const viaCode = workerFieldCodes.viaCode || 'via_destination';
      const introducerCode = workerFieldCodes.introducerCode || 'introducer_supplier';
      const introducer = getWorkerIntroducer(record);
      const phone = record.phone && record.phone.value ? String(record.phone.value) : '';
      const email = record.email && record.email.value ? String(record.email.value) : '';
      const pref = record.pref && record.pref.value ? String(record.pref.value) : '';
      const city = record.city_etc && record.city_etc.value ? String(record.city_etc.value) : '';
      const building = record.name_of_building && record.name_of_building.value ? String(record.name_of_building.value) : '';
      const active = record.is_active && record.is_active.value ? String(record.is_active.value) : '';

      function closeAuxOverlay(auxOverlay) {
        if (auxOverlay && auxOverlay.parentNode) {
          auxOverlay.parentNode.removeChild(auxOverlay);
        }
      }

      function openPayoutCreateFromWorkerModal() {
        if (!workerId) {
          alert('稼働者IDが取得できませんでした');
          return;
        }

        const now = new Date();
        const createOverlay = document.createElement('div');
        createOverlay.className = 'vanzai-modal-overlay';
        createOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:10002;display:flex;align-items:center;justify-content:center;';

        const createModal = document.createElement('div');
        createModal.className = 'vanzai-modal';
        createModal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.22);width:92%;max-width:420px;overflow:hidden;';

        const head = document.createElement('div');
        head.style.cssText = 'padding:14px 16px;border-bottom:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#111827;';
        head.textContent = '支払明細の作成';

        const body = document.createElement('div');
        body.style.cssText = 'padding:16px;display:flex;flex-direction:column;gap:12px;';

        const info = document.createElement('div');
        info.style.cssText = 'font-size:13px;color:#374151;';
        info.textContent = `対象稼働者: ${workerId}`;
        body.appendChild(info);

        const ymWrap = document.createElement('div');
        ymWrap.style.cssText = 'display:flex;gap:8px;';

        const yearInput = document.createElement('input');
        yearInput.type = 'number';
        yearInput.value = String(now.getFullYear());
        yearInput.min = '2000';
        yearInput.max = '2100';
        yearInput.style.cssText = 'flex:1;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';

        const monthInput = document.createElement('input');
        monthInput.type = 'number';
        monthInput.value = String(now.getMonth() + 1);
        monthInput.min = '1';
        monthInput.max = '12';
        monthInput.style.cssText = 'width:100px;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';

        ymWrap.appendChild(yearInput);
        ymWrap.appendChild(monthInput);
        body.appendChild(ymWrap);

        const footer = document.createElement('div');
        footer.style.cssText = 'padding:12px 16px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:8px;';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '閉じる';
        cancelBtn.className = 'kintoneplugin-button-dialog-cancel';
        cancelBtn.style.cssText = 'padding:8px 16px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:13px;';
        cancelBtn.onclick = () => closeAuxOverlay(createOverlay);

        const goBtn = document.createElement('button');
        goBtn.textContent = '作成';
        goBtn.className = 'kintoneplugin-button-dialog-ok';
        goBtn.style.cssText = 'padding:8px 16px;border:none;border-radius:4px;background:#10b981;color:white;cursor:pointer;font-size:13px;font-weight:600;';
        goBtn.onclick = async () => {
          const y = Number(yearInput.value);
          const m = Number(monthInput.value);
          if (!Number.isFinite(y) || y < 2000 || y > 2100) {
            alert('年を正しく入力してください（2000〜2100）');
            return;
          }
          if (!Number.isFinite(m) || m < 1 || m > 12) {
            alert('月を正しく入力してください（1〜12）');
            return;
          }

          goBtn.disabled = true;
          goBtn.textContent = '作成中...';
          try {
            const periodKey = toPeriodKey(y, m);
            const payoutFields = await resolvePayoutFieldCodes();
            let targetWorkerId = workerId;
            let supplierId = '';
            if (viaDestination === '下請け' && introducer) {
              const confirmed = window.confirm('下請けの稼働者のため、紹介元の下請けへの支払明細を作成しますか？');
              if (!confirmed) {
                closeAuxOverlay(createOverlay);
                return;
              }
              supplierId = String(introducer || '').trim();
              targetWorkerId = supplierId || workerId;
            }

            const result = await ensurePayoutRecordExists(payoutFields, periodKey, targetWorkerId, { supplierId });
            if (!result.recordId) {
              throw new Error('支払明細レコードIDの取得に失敗しました');
            }
            const pdfResult = await generateAndAttachPayoutPdf(payoutFields, result.recordId);
            closeAuxOverlay(createOverlay);
            const storageLabel = pdfResult.storage === 'kintone'
              ? 'Kintone添付'
              : (pdfResult.storage === 'external' ? '外部ストレージ保存' : 'ローカル保存');
            const urlSavedLine = pdfResult.storage === 'external'
              ? `URL保存: ${pdfResult.urlSaved ? 'App173に保存済み' : '未保存（URLフィールド未設定）'}`
              : '';
            showStyledDialog(
              `${result.created ? '支払明細を作成しました' : '既存支払明細を更新しました'}\n${periodKey} / ${supplierId || workerId}\nPDF: ${pdfResult.fileName}\n保存先: ${storageLabel}${urlSavedLine ? `\n${urlSavedLine}` : ''}`,
              {
                kind: 'success',
                title: '処理結果',
                detailButtonLabel: '詳細確認',
                onDetail: () => {
                  if (result.recordId) {
                    openAppRecord(payoutFields.appId, result.recordId);
                  } else {
                    openAppWithQuery(payoutFields.appId, result.query);
                  }
                }
              }
            );
          } catch (err) {
            alert(err && err.message ? err.message : '支払明細の作成に失敗しました');
          } finally {
            goBtn.disabled = false;
            goBtn.textContent = '作成';
          }
        };

        footer.appendChild(cancelBtn);
        footer.appendChild(goBtn);
        createModal.appendChild(head);
        createModal.appendChild(body);
        createModal.appendChild(footer);
        createOverlay.appendChild(createModal);
        document.body.appendChild(createOverlay);
      }

      function openPayoutReferenceFromWorkerModal() {
        if (!workerId) {
          alert('稼働者IDが取得できませんでした');
          return;
        }

        const refOverlay = document.createElement('div');
        refOverlay.className = 'vanzai-modal-overlay';
        refOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:10002;display:flex;align-items:center;justify-content:center;';

        const refModal = document.createElement('div');
        refModal.className = 'vanzai-modal';
        refModal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.22);width:94%;max-width:700px;max-height:86vh;overflow:hidden;display:flex;flex-direction:column;';

        const head = document.createElement('div');
        head.style.cssText = 'padding:14px 16px;border-bottom:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#111827;';
        head.textContent = `支払明細の参照（${workerId}）`;

        const body = document.createElement('div');
        body.style.cssText = 'padding:16px;display:flex;flex-direction:column;gap:10px;overflow:auto;';

        const filterWrap = document.createElement('div');
        filterWrap.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;';

        const now = new Date();
        const refYearInput = document.createElement('input');
        refYearInput.type = 'number';
        refYearInput.min = '2000';
        refYearInput.max = '2100';
        refYearInput.value = String(now.getFullYear());
        refYearInput.style.cssText = 'width:120px;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;';

        const refMonthInput = document.createElement('input');
        refMonthInput.type = 'number';
        refMonthInput.min = '1';
        refMonthInput.max = '12';
        refMonthInput.value = String(now.getMonth() + 1);
        refMonthInput.style.cssText = 'width:90px;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;';

        const filterBtn = document.createElement('button');
        filterBtn.textContent = '年月で絞り込み';
        filterBtn.style.cssText = 'padding:8px 12px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:13px;font-weight:600;color:#374151;';

        const clearFilterBtn = document.createElement('button');
        clearFilterBtn.textContent = '絞り込み解除';
        clearFilterBtn.style.cssText = 'padding:8px 12px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:13px;color:#6b7280;';

        filterWrap.appendChild(refYearInput);
        filterWrap.appendChild(refMonthInput);
        filterWrap.appendChild(filterBtn);
        filterWrap.appendChild(clearFilterBtn);
        body.appendChild(filterWrap);

        const status = document.createElement('div');
        status.style.cssText = 'font-size:13px;color:#6b7280;';
        status.textContent = 'PDFを読み込み中...';
        body.appendChild(status);

        const pdfSelect = document.createElement('select');
        pdfSelect.style.cssText = 'width:100%;padding:9px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;background:white;';
        pdfSelect.disabled = true;
        body.appendChild(pdfSelect);

        const footer = document.createElement('div');
        footer.style.cssText = 'padding:12px 16px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:8px;';

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '閉じる';
        closeBtn.className = 'kintoneplugin-button-dialog-cancel';
        closeBtn.style.cssText = 'padding:8px 16px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:13px;';
        closeBtn.onclick = () => closeAuxOverlay(refOverlay);

        const openPdfBtn = document.createElement('button');
        openPdfBtn.textContent = 'PDFを開く';
        openPdfBtn.className = 'kintoneplugin-button-dialog-ok';
        openPdfBtn.style.cssText = 'padding:8px 16px;border:none;border-radius:4px;background:#2563eb;color:white;cursor:pointer;font-size:13px;font-weight:600;';
        openPdfBtn.disabled = true;

        let selectableFiles = [];

        const loadPdfOptions = (periodKey) => {
          status.textContent = periodKey
            ? `${periodKey} のPDFを読み込み中...`
            : 'PDFを読み込み中...';
          pdfSelect.disabled = true;
          openPdfBtn.disabled = true;

          return resolvePayoutFieldCodes().then((payoutFields) => {
            if (!payoutFields.attachmentCode) {
              throw new Error('支払明細アプリにPDF添付フィールドが見つかりません');
            }

            const whereParts = [buildKintoneFieldCondition(payoutFields.workerCode, payoutFields.workerFieldType, workerId)];
            if (periodKey) {
              whereParts.push(buildKintoneFieldCondition(payoutFields.periodCode, payoutFields.periodType, periodKey));
            }
            const query = `${whereParts.join(' and ')} order by ${payoutFields.periodCode} desc, $id desc limit 500`;

            return fetchRecords(
              payoutFields.appId,
              query,
              [payoutFields.periodCode, payoutFields.payoutIdCode, payoutFields.attachmentCode]
            ).then((records) => ({ records, payoutFields }));
          }).then(({ records, payoutFields }) => {
            selectableFiles = [];
            records.forEach((record) => {
              const period = getFieldValue(record, payoutFields.periodCode).trim() || '-';
              const payoutId = getFieldValue(record, payoutFields.payoutIdCode).trim() || '-';
              const files = (record[payoutFields.attachmentCode] && record[payoutFields.attachmentCode].value) || [];
              files.forEach((file, idx) => {
                if (!file || !file.fileKey) {
                  return;
                }
                const fileName = file.name ? String(file.name) : `${payoutId}_${idx + 1}.pdf`;
                selectableFiles.push({
                  fileKey: String(file.fileKey),
                  label: `${period} / ${payoutId} / ${fileName}`
                });
              });
            });

            pdfSelect.innerHTML = '';
            const emptyOpt = document.createElement('option');
            emptyOpt.value = '';
            emptyOpt.textContent = selectableFiles.length
              ? `PDFを選択してください（${selectableFiles.length}件）`
              : '作成済みPDFがありません';
            pdfSelect.appendChild(emptyOpt);

            selectableFiles.forEach((item) => {
              const opt = document.createElement('option');
              opt.value = item.fileKey;
              opt.textContent = item.label;
              pdfSelect.appendChild(opt);
            });

            status.textContent = selectableFiles.length
              ? '過去に作成したPDFを選択できます。'
              : '過去に作成したPDFはまだありません。';
            pdfSelect.disabled = selectableFiles.length === 0;
            updateOpenButton();
          }).catch((err) => {
            status.textContent = err && err.message ? err.message : 'PDFの取得に失敗しました';
            pdfSelect.innerHTML = '';
            const failOpt = document.createElement('option');
            failOpt.value = '';
            failOpt.textContent = '読み込みに失敗しました';
            pdfSelect.appendChild(failOpt);
            pdfSelect.disabled = true;
            openPdfBtn.disabled = true;
          });
        };

        const updateOpenButton = () => {
          openPdfBtn.disabled = !pdfSelect.value;
        };

        pdfSelect.addEventListener('change', updateOpenButton);

        filterBtn.onclick = () => {
          const y = Number(refYearInput.value);
          const m = Number(refMonthInput.value);
          if (!Number.isFinite(y) || y < 2000 || y > 2100) {
            alert('年を正しく入力してください（2000〜2100）');
            return;
          }
          if (!Number.isFinite(m) || m < 1 || m > 12) {
            alert('月を正しく入力してください（1〜12）');
            return;
          }
          const periodKey = toPeriodKey(y, m);
          loadPdfOptions(periodKey);
        };

        clearFilterBtn.onclick = () => {
          loadPdfOptions('');
        };

        openPdfBtn.onclick = async () => {
          const fileKey = pdfSelect.value;
          if (!fileKey) {
            return;
          }
          const target = selectableFiles.find((item) => item.fileKey === fileKey);
          if (!target) {
            alert('選択したPDFが見つかりません。再読み込みしてください。');
            return;
          }

          openPdfBtn.disabled = true;
          openPdfBtn.textContent = '取得中...';
          try {
            const blob = await fetchFileBlobByKey(fileKey);
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
            setTimeout(() => URL.revokeObjectURL(url), 60000);
          } catch (err) {
            alert(err && err.message ? err.message : 'PDFの取得に失敗しました');
          } finally {
            openPdfBtn.textContent = 'PDFを開く';
            updateOpenButton();
          }
        };

        footer.appendChild(closeBtn);
        footer.appendChild(openPdfBtn);
        refModal.appendChild(head);
        refModal.appendChild(body);
        refModal.appendChild(footer);
        refOverlay.appendChild(refModal);
        document.body.appendChild(refOverlay);

        loadPdfOptions(toPeriodKey(now.getFullYear(), now.getMonth() + 1));
      }

      payoutCreateButton.onclick = () => openPayoutCreateFromWorkerModal();
      payoutReferenceButton.onclick = () => openPayoutReferenceFromWorkerModal();

      const detailItems = [
        { label: '稼働者ID', code: 'worker_id', value: workerId, editable: false },
        { label: '氏名(姓)', code: 'last_name', value: lastName, editable: true },
        { label: '氏名(名)', code: 'first_name', value: firstName, editable: true },
        { label: '姓(フリガナ)', code: 'lastname_furigana', value: lastKana, editable: true },
        { label: '名(フリガナ)', code: 'firstname_furigana', value: firstKana, editable: true },
        { label: '経由先', code: viaCode, value: viaDestination, editable: true, type: 'select', options: ['下請け', '紹介', 'VANZAI直接'] },
        { label: '紹介者/下請け', code: introducerCode, value: introducer, editable: true },
        { label: '電話', code: 'phone', value: phone, editable: true },
        { label: 'メール', code: 'email', value: email, editable: true },
        { label: '都道府県', code: 'pref', value: pref, editable: true },
        { label: '市区町村以下', code: 'city_etc', value: city, editable: true },
        { label: '建物名・部屋番号', code: 'name_of_building', value: building, editable: true },
        { label: '有効・無効', code: 'is_active', value: active, editable: true, type: 'select', options: ['有効', '無効'] },
      ];

      const detailTable = document.createElement('table');
      detailTable.style.cssText = 'width:100%;border-collapse:collapse;font-size:14px;';

      const editInputs = {};

      detailItems.forEach((item) => {
        const tr = document.createElement('tr');
        tr.style.cssText = 'border-bottom:1px solid #e5e7eb;';

        const th = document.createElement('th');
        th.textContent = item.label;
        th.style.cssText = 'width:180px;padding:10px 8px;text-align:left;color:#374151;background:#f9fafb;vertical-align:top;';

        const td = document.createElement('td');
        td.style.cssText = 'padding:10px 8px;color:#111827;word-break:break-word;';

        if (!item.editable) {
          td.textContent = item.value || '';
        } else if (item.type === 'select') {
          const select = document.createElement('select');
          select.style.cssText = 'width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';
          (item.options || []).forEach((opt) => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            select.appendChild(option);
          });
          select.value = item.value || '';
          td.appendChild(select);
          editInputs[item.code] = select;
        } else {
          const input = document.createElement('input');
          input.type = 'text';
          input.value = item.value || '';
          input.style.cssText = 'width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';
          td.appendChild(input);
          editInputs[item.code] = input;
        }

        tr.appendChild(th);
        tr.appendChild(td);
        detailTable.appendChild(tr);
      });

      const viaInput = editInputs[viaCode];
      const introducerInput = editInputs[introducerCode];
      const syncIntroducerByVia = () => {
        if (!introducerInput) {
          return;
        }
        const viaValue = viaInput ? normalizeViaDestination(viaInput.value) : '';
        const isDirect = isDirectViaDestination(viaValue);
        if (viaInput && viaInput.value !== viaValue) {
          viaInput.value = viaValue;
        }
        if (isDirect) {
          introducerInput.value = '';
        }
        introducerInput.disabled = isDirect;
        introducerInput.style.background = isDirect ? '#f3f4f6' : 'white';
        introducerInput.style.color = isDirect ? '#6b7280' : '#111827';
        introducerInput.style.cursor = isDirect ? 'not-allowed' : 'text';
      };

      if (viaInput) {
        viaInput.addEventListener('change', syncIntroducerByVia);
      }
      syncIntroducerByVia();

      detailBody.appendChild(detailTable);

      const detailFooter = document.createElement('div');
      detailFooter.style.cssText = 'padding:16px 20px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:12px;';

      const saveButton = document.createElement('button');
      saveButton.textContent = '保存';
      saveButton.className = 'kintoneplugin-button-dialog-ok';
      saveButton.style.cssText = 'padding:10px 24px;border:none;border-radius:4px;background:#10b981;color:white;cursor:pointer;font-size:14px;font-weight:600;';
      saveButton.onclick = () => {
        const recordId = record.$id && record.$id.value ? String(record.$id.value) : '';
        if (!recordId) {
          alert('レコードIDが取得できませんでした');
          return;
        }

        const nextLastName = editInputs.last_name ? String(editInputs.last_name.value || '').trim() : '';
        const nextFirstName = editInputs.first_name ? String(editInputs.first_name.value || '').trim() : '';
        if (!nextLastName || !nextFirstName) {
          alert('氏名(姓)と氏名(名)は必須です');
          return;
        }

        const viaValue = viaInput ? normalizeViaDestination(viaInput.value) : '';
        const introducerValue = editInputs[introducerCode] ? String(editInputs[introducerCode].value || '').trim() : '';
        const isDirect = isDirectViaDestination(viaValue);
        if (!viaValue) {
          alert('経由先は必須です');
          return;
        }
        if (!isDirect && !introducerValue) {
          alert('紹介者/下請けは必須です（経由先がVANZAI直接以外）');
          return;
        }
        const payload = {
          last_name: { value: nextLastName },
          first_name: { value: nextFirstName },
          lastname_furigana: { value: editInputs.lastname_furigana ? String(editInputs.lastname_furigana.value || '').trim() : '' },
          firstname_furigana: { value: editInputs.firstname_furigana ? String(editInputs.firstname_furigana.value || '').trim() : '' },
          [viaCode]: { value: viaValue },
          [introducerCode]: { value: isDirect ? '' : introducerValue },
          phone: { value: editInputs.phone ? String(editInputs.phone.value || '').trim() : '' },
          email: { value: editInputs.email ? String(editInputs.email.value || '').trim() : '' },
          pref: { value: editInputs.pref ? String(editInputs.pref.value || '').trim() : '' },
          city_etc: { value: editInputs.city_etc ? String(editInputs.city_etc.value || '').trim() : '' },
          name_of_building: { value: editInputs.name_of_building ? String(editInputs.name_of_building.value || '').trim() : '' },
          is_active: { value: editInputs.is_active ? String(editInputs.is_active.value || '').trim() : '' },
        };

        console.info('稼働者詳細を保存します', { worker_id: workerId, record_id: recordId });
        saveButton.disabled = true;
        saveButton.textContent = '保存中...';

        kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/record.json`, 'PUT', {
          app: CONFIG.apps.workers,
          id: recordId,
          record: payload,
        }).then(() => {
          console.info('稼働者詳細を保存しました', { worker_id: workerId, record_id: recordId });
          WORKERS_ALL_CACHE = null;
          WORKERS_CACHE = null;
          showToast('更新しました');
          document.body.style.overflow = '';
          document.body.removeChild(detailOverlay);
          openWorkerListModal();
        }).catch((err) => {
          console.error('稼働者詳細保存エラー:', err);
          alert('保存に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
        }).finally(() => {
          saveButton.disabled = false;
          saveButton.textContent = '保存';
        });
      };
      detailFooter.appendChild(saveButton);

      const detailCloseButton = document.createElement('button');
      detailCloseButton.textContent = '閉じる';
      detailCloseButton.className = 'kintoneplugin-button-dialog-cancel';
      detailCloseButton.style.cssText = 'padding:10px 24px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:14px;';
      detailCloseButton.onclick = () => {
        document.body.style.overflow = '';
        document.body.removeChild(detailOverlay);
      };
      detailFooter.appendChild(detailCloseButton);

      detailModal.appendChild(detailHeader);
      detailModal.appendChild(detailBody);
      detailModal.appendChild(detailFooter);
      detailOverlay.appendChild(detailModal);

      document.body.style.overflow = 'hidden';
      document.body.appendChild(detailOverlay);
    }

    fetchAllWorkers().then((records) => {
      workerRecords = records || [];
      syncFilterOptions();
      updateWorkerHeaderSortIndicators();
      renderWorkerRows();
    }).catch((err) => {
      console.error('稼働者一覧取得エラー:', err);
      tbody.innerHTML = '<tr><td colspan="8" style="padding:20px;text-align:center;color:#ef4444;">データの取得に失敗しました</td></tr>';
    });

    document.body.style.overflow = 'hidden';
    document.body.appendChild(overlay);
  }

  function openVanzaiStaffListModal() {
    let staffRecords = [];
    const staffListSort = { column: 'id', direction: 'asc' };
    const staffListColumns = [
      { key: 'id', label: 'ID', sortable: true },
      { key: 'name', label: '職員名', sortable: true },
      { key: 'role', label: '役職', sortable: true },
      { key: 'phone', label: '電話番号', sortable: false },
      { key: 'mail', label: 'メールアドレス', sortable: false },
    ];
    const staffListHeaderCells = {};

    const getStaffValue = (record, key) => {
      if (!record || !record[key] || !record[key].value) {
        if (key === 'role' && record) {
          const fallbackKeys = ['staff_role', 'position', 'job_title'];
          for (let i = 0; i < fallbackKeys.length; i += 1) {
            const fallback = fallbackKeys[i];
            if (record[fallback] && record[fallback].value) {
              return String(record[fallback].value);
            }
          }
        }
        return '';
      }
      return String(record[key].value);
    };

    const sortStaffRecords = (records) => {
      const sorted = (records || []).slice();
      const column = staffListSort.column;
      const direction = staffListSort.direction === 'desc' ? -1 : 1;
      sorted.sort((a, b) => {
        const av = String(getStaffValue(a, column) || '');
        const bv = String(getStaffValue(b, column) || '');
        return av.localeCompare(bv, 'ja', { numeric: true, sensitivity: 'base' }) * direction;
      });
      return sorted;
    };

    const updateStaffHeaderSortIndicators = () => {
      Object.keys(staffListHeaderCells).forEach((key) => {
        const th = staffListHeaderCells[key];
        const col = staffListColumns.find((item) => item.key === key);
        if (!th || !col) {
          return;
        }
        if (!col.sortable) {
          th.textContent = col.label;
          return;
        }
        const marker = staffListSort.column === key
          ? (staffListSort.direction === 'asc' ? ' ▲' : ' ▼')
          : ' ▽';
        th.textContent = `${col.label}${marker}`;
      });
    };

    const overlay = document.createElement('div');
    overlay.className = 'vanzai-modal-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';

    const modal = document.createElement('div');
    modal.className = 'vanzai-modal';
    modal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);width:95%;max-width:1100px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column;';

    const header = document.createElement('div');
    header.style.cssText = 'padding:20px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;background:#4A90E2;color:white;';
    const title = document.createElement('h2');
    title.textContent = '職員一覧';
    title.style.cssText = 'margin:0;font-size:18px;font-weight:600;';
    header.appendChild(title);

    const tableWrapper = document.createElement('div');
    tableWrapper.style.cssText = 'overflow:auto;flex:1;padding:20px;';

    const table = document.createElement('table');
    table.style.cssText = 'width:100%;border-collapse:collapse;font-size:13px;';
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.style.cssText = 'background:linear-gradient(to right,#f3f4f6,#e5e7eb);';
    staffListColumns.forEach((column) => {
      const th = document.createElement('th');
      th.textContent = column.label;
      th.style.cssText = 'padding:12px 8px;text-align:left;border-bottom:2px solid #d1d5db;font-weight:600;white-space:nowrap;';
      if (column.sortable) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.onclick = () => {
          if (staffListSort.column === column.key) {
            staffListSort.direction = staffListSort.direction === 'asc' ? 'desc' : 'asc';
          } else {
            staffListSort.column = column.key;
            staffListSort.direction = 'asc';
          }
          updateStaffHeaderSortIndicators();
          renderStaffRows();
        };
      }
      staffListHeaderCells[column.key] = th;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    updateStaffHeaderSortIndicators();

    const tbody = document.createElement('tbody');
    table.appendChild(tbody);
    tableWrapper.appendChild(table);

    const footer = document.createElement('div');
    footer.style.cssText = 'padding:16px 20px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:12px;';
    const closeButton = document.createElement('button');
    closeButton.textContent = '閉じる';
    closeButton.className = 'kintoneplugin-button-dialog-cancel';
    closeButton.style.cssText = 'padding:10px 24px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:14px;';
    closeButton.onclick = () => {
      document.body.style.overflow = '';
      document.body.removeChild(overlay);
    };
    footer.appendChild(closeButton);

    modal.appendChild(header);
    modal.appendChild(tableWrapper);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    function openStaffDetailModal(record) {
      const detailOverlay = document.createElement('div');
      detailOverlay.className = 'vanzai-modal-overlay';
      detailOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10001;display:flex;align-items:center;justify-content:center;';

      const detailModal = document.createElement('div');
      detailModal.className = 'vanzai-modal';
      detailModal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);width:92%;max-width:760px;max-height:88vh;overflow:hidden;display:flex;flex-direction:column;';

      const detailHeader = document.createElement('div');
      detailHeader.style.cssText = 'padding:20px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;background:#4A90E2;color:white;';
      const detailTitle = document.createElement('h2');
      detailTitle.textContent = '職員詳細';
      detailTitle.style.cssText = 'margin:0;font-size:18px;font-weight:600;';
      detailHeader.appendChild(detailTitle);

      const detailHeaderActions = document.createElement('div');
      detailHeaderActions.style.cssText = 'display:flex;align-items:center;gap:8px;';

      const payoutCreateButton = document.createElement('button');
      payoutCreateButton.textContent = '支払明細の作成';
      payoutCreateButton.style.cssText = 'padding:8px 12px;border:1px solid #34d399;border-radius:6px;background:#10b981;color:white;cursor:pointer;font-size:13px;font-weight:600;';

      const payoutReferenceButton = document.createElement('button');
      payoutReferenceButton.textContent = '支払明細の参照';
      payoutReferenceButton.style.cssText = 'padding:8px 12px;border:1px solid #93c5fd;border-radius:6px;background:#2563eb;color:white;cursor:pointer;font-size:13px;font-weight:600;';

      detailHeaderActions.appendChild(payoutCreateButton);
      detailHeaderActions.appendChild(payoutReferenceButton);
      detailHeader.appendChild(detailHeaderActions);

      const detailBody = document.createElement('div');
      detailBody.style.cssText = 'padding:20px;overflow:auto;';

      const staffId = getStaffValue(record, 'id');
      const name = getStaffValue(record, 'name');
      const role = getStaffValue(record, 'role');
      const phone = getStaffValue(record, 'phone');
      const mail = getStaffValue(record, 'mail');
      const memo = getStaffValue(record, 'memo');

      function closeAuxOverlay(auxOverlay) {
        if (auxOverlay && auxOverlay.parentNode) {
          auxOverlay.parentNode.removeChild(auxOverlay);
        }
      }

      function openPayoutCreateFromStaffModal() {
        if (!staffId) {
          alert('職員IDが取得できませんでした');
          return;
        }

        const now = new Date();
        const createOverlay = document.createElement('div');
        createOverlay.className = 'vanzai-modal-overlay';
        createOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:10002;display:flex;align-items:center;justify-content:center;';

        const createModal = document.createElement('div');
        createModal.className = 'vanzai-modal';
        createModal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.22);width:92%;max-width:420px;overflow:hidden;';

        const head = document.createElement('div');
        head.style.cssText = 'padding:14px 16px;border-bottom:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#111827;';
        head.textContent = '支払明細の作成';

        const body = document.createElement('div');
        body.style.cssText = 'padding:16px;display:flex;flex-direction:column;gap:12px;';

        const info = document.createElement('div');
        info.style.cssText = 'font-size:13px;color:#374151;';
        info.textContent = `対象職員: ${staffId}`;
        body.appendChild(info);

        const ymWrap = document.createElement('div');
        ymWrap.style.cssText = 'display:flex;gap:8px;';

        const yearInput = document.createElement('input');
        yearInput.type = 'number';
        yearInput.value = String(now.getFullYear());
        yearInput.min = '2000';
        yearInput.max = '2100';
        yearInput.style.cssText = 'flex:1;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';

        const monthInput = document.createElement('input');
        monthInput.type = 'number';
        monthInput.value = String(now.getMonth() + 1);
        monthInput.min = '1';
        monthInput.max = '12';
        monthInput.style.cssText = 'width:100px;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';

        ymWrap.appendChild(yearInput);
        ymWrap.appendChild(monthInput);
        body.appendChild(ymWrap);

        const footer = document.createElement('div');
        footer.style.cssText = 'padding:12px 16px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:8px;';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '閉じる';
        cancelBtn.className = 'kintoneplugin-button-dialog-cancel';
        cancelBtn.style.cssText = 'padding:8px 16px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:13px;';
        cancelBtn.onclick = () => closeAuxOverlay(createOverlay);

        const goBtn = document.createElement('button');
        goBtn.textContent = '作成';
        goBtn.className = 'kintoneplugin-button-dialog-ok';
        goBtn.style.cssText = 'padding:8px 16px;border:none;border-radius:4px;background:#10b981;color:white;cursor:pointer;font-size:13px;font-weight:600;';
        goBtn.onclick = async () => {
          const y = Number(yearInput.value);
          const m = Number(monthInput.value);
          if (!Number.isFinite(y) || y < 2000 || y > 2100) {
            alert('年を正しく入力してください（2000〜2100）');
            return;
          }
          if (!Number.isFinite(m) || m < 1 || m > 12) {
            alert('月を正しく入力してください（1〜12）');
            return;
          }

          goBtn.disabled = true;
          goBtn.textContent = '作成中...';
          try {
            const periodKey = toPeriodKey(y, m);
            const payoutFields = await resolvePayoutFieldCodes();
            const result = await ensurePayoutRecordExists(payoutFields, periodKey, staffId, { supplierId: '' });
            if (!result.recordId) {
              throw new Error('支払明細レコードIDの取得に失敗しました');
            }
            const pdfResult = await generateAndAttachPayoutPdf(payoutFields, result.recordId);
            closeAuxOverlay(createOverlay);
            const storageLabel = pdfResult.storage === 'kintone'
              ? 'Kintone添付'
              : (pdfResult.storage === 'external' ? '外部ストレージ保存' : 'ローカル保存');
            showStyledDialog(
              `${result.created ? '支払明細を作成しました' : '既存支払明細を更新しました'}\n${periodKey} / ${staffId}\nPDF: ${pdfResult.fileName}\n保存先: ${storageLabel}`,
              {
                kind: 'success',
                title: '処理結果',
                detailButtonLabel: '詳細確認',
                onDetail: () => {
                  if (result.recordId) {
                    openAppRecord(payoutFields.appId, result.recordId);
                  } else {
                    openAppWithQuery(payoutFields.appId, result.query);
                  }
                }
              }
            );
          } catch (err) {
            alert(err && err.message ? err.message : '支払明細の作成に失敗しました');
          } finally {
            goBtn.disabled = false;
            goBtn.textContent = '作成';
          }
        };

        footer.appendChild(cancelBtn);
        footer.appendChild(goBtn);
        createModal.appendChild(head);
        createModal.appendChild(body);
        createModal.appendChild(footer);
        createOverlay.appendChild(createModal);
        document.body.appendChild(createOverlay);
      }

      function openPayoutReferenceFromStaffModal() {
        if (!staffId) {
          alert('職員IDが取得できませんでした');
          return;
        }

        const refOverlay = document.createElement('div');
        refOverlay.className = 'vanzai-modal-overlay';
        refOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:10002;display:flex;align-items:center;justify-content:center;';

        const refModal = document.createElement('div');
        refModal.className = 'vanzai-modal';
        refModal.style.cssText = 'background:white;border-radius:8px;box-shadow:0 8px 20px rgba(0,0,0,0.22);width:94%;max-width:700px;max-height:86vh;overflow:hidden;display:flex;flex-direction:column;';

        const head = document.createElement('div');
        head.style.cssText = 'padding:14px 16px;border-bottom:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#111827;';
        head.textContent = `支払明細の参照（${staffId}）`;

        const body = document.createElement('div');
        body.style.cssText = 'padding:16px;display:flex;flex-direction:column;gap:10px;overflow:auto;';

        const filterWrap = document.createElement('div');
        filterWrap.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;';

        const now = new Date();
        const refYearInput = document.createElement('input');
        refYearInput.type = 'number';
        refYearInput.min = '2000';
        refYearInput.max = '2100';
        refYearInput.value = String(now.getFullYear());
        refYearInput.style.cssText = 'width:120px;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;';

        const refMonthInput = document.createElement('input');
        refMonthInput.type = 'number';
        refMonthInput.min = '1';
        refMonthInput.max = '12';
        refMonthInput.value = String(now.getMonth() + 1);
        refMonthInput.style.cssText = 'width:90px;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;';

        const filterBtn = document.createElement('button');
        filterBtn.textContent = '年月で絞り込み';
        filterBtn.style.cssText = 'padding:8px 12px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:13px;font-weight:600;color:#374151;';

        const clearFilterBtn = document.createElement('button');
        clearFilterBtn.textContent = '絞り込み解除';
        clearFilterBtn.style.cssText = 'padding:8px 12px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:13px;color:#6b7280;';

        filterWrap.appendChild(refYearInput);
        filterWrap.appendChild(refMonthInput);
        filterWrap.appendChild(filterBtn);
        filterWrap.appendChild(clearFilterBtn);
        body.appendChild(filterWrap);

        const status = document.createElement('div');
        status.style.cssText = 'font-size:13px;color:#6b7280;';
        status.textContent = 'PDFを読み込み中...';
        body.appendChild(status);

        const pdfSelect = document.createElement('select');
        pdfSelect.style.cssText = 'width:100%;padding:9px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;background:white;';
        pdfSelect.disabled = true;
        body.appendChild(pdfSelect);

        const footer = document.createElement('div');
        footer.style.cssText = 'padding:12px 16px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:8px;';

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '閉じる';
        closeBtn.className = 'kintoneplugin-button-dialog-cancel';
        closeBtn.style.cssText = 'padding:8px 16px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:13px;';
        closeBtn.onclick = () => closeAuxOverlay(refOverlay);

        const openPdfBtn = document.createElement('button');
        openPdfBtn.textContent = 'PDFを開く';
        openPdfBtn.className = 'kintoneplugin-button-dialog-ok';
        openPdfBtn.style.cssText = 'padding:8px 16px;border:none;border-radius:4px;background:#2563eb;color:white;cursor:pointer;font-size:13px;font-weight:600;';
        openPdfBtn.disabled = true;

        let selectableFiles = [];

        const loadPdfOptions = (periodKey) => {
          status.textContent = periodKey ? `${periodKey} のPDFを読み込み中...` : 'PDFを読み込み中...';
          pdfSelect.disabled = true;
          openPdfBtn.disabled = true;

          return resolvePayoutFieldCodes().then((payoutFields) => {
            if (!payoutFields.attachmentCode) {
              throw new Error('支払明細アプリにPDF添付フィールドが見つかりません');
            }
            const whereParts = [buildKintoneFieldCondition(payoutFields.workerCode, payoutFields.workerFieldType, staffId)];
            if (periodKey) {
              whereParts.push(buildKintoneFieldCondition(payoutFields.periodCode, payoutFields.periodType, periodKey));
            }
            const query = `${whereParts.join(' and ')} order by ${payoutFields.periodCode} desc, $id desc limit 500`;
            return fetchRecords(
              payoutFields.appId,
              query,
              [payoutFields.periodCode, payoutFields.payoutIdCode, payoutFields.attachmentCode]
            ).then((records) => ({ records, payoutFields }));
          }).then(({ records, payoutFields }) => {
            selectableFiles = [];
            records.forEach((payoutRecord) => {
              const period = getFieldValue(payoutRecord, payoutFields.periodCode).trim() || '-';
              const payoutId = getFieldValue(payoutRecord, payoutFields.payoutIdCode).trim() || '-';
              const files = (payoutRecord[payoutFields.attachmentCode] && payoutRecord[payoutFields.attachmentCode].value) || [];
              files.forEach((file, idx) => {
                if (!file || !file.fileKey) {
                  return;
                }
                const fileName = file.name ? String(file.name) : `${payoutId}_${idx + 1}.pdf`;
                selectableFiles.push({
                  fileKey: String(file.fileKey),
                  label: `${period} / ${payoutId} / ${fileName}`
                });
              });
            });

            pdfSelect.innerHTML = '';
            const emptyOpt = document.createElement('option');
            emptyOpt.value = '';
            emptyOpt.textContent = selectableFiles.length
              ? `PDFを選択してください（${selectableFiles.length}件）`
              : '作成済みPDFがありません';
            pdfSelect.appendChild(emptyOpt);

            selectableFiles.forEach((item) => {
              const opt = document.createElement('option');
              opt.value = item.fileKey;
              opt.textContent = item.label;
              pdfSelect.appendChild(opt);
            });

            status.textContent = selectableFiles.length
              ? '過去に作成したPDFを選択できます。'
              : '過去に作成したPDFはまだありません。';
            pdfSelect.disabled = selectableFiles.length === 0;
            updateOpenButton();
          }).catch((err) => {
            status.textContent = err && err.message ? err.message : 'PDFの取得に失敗しました';
            pdfSelect.innerHTML = '';
            const failOpt = document.createElement('option');
            failOpt.value = '';
            failOpt.textContent = '読み込みに失敗しました';
            pdfSelect.appendChild(failOpt);
            pdfSelect.disabled = true;
            openPdfBtn.disabled = true;
          });
        };

        const updateOpenButton = () => {
          openPdfBtn.disabled = !pdfSelect.value;
        };

        pdfSelect.addEventListener('change', updateOpenButton);

        filterBtn.onclick = () => {
          const y = Number(refYearInput.value);
          const m = Number(refMonthInput.value);
          if (!Number.isFinite(y) || y < 2000 || y > 2100) {
            alert('年を正しく入力してください（2000〜2100）');
            return;
          }
          if (!Number.isFinite(m) || m < 1 || m > 12) {
            alert('月を正しく入力してください（1〜12）');
            return;
          }
          loadPdfOptions(toPeriodKey(y, m));
        };

        clearFilterBtn.onclick = () => {
          loadPdfOptions('');
        };

        openPdfBtn.onclick = async () => {
          const fileKey = pdfSelect.value;
          if (!fileKey) {
            return;
          }
          const target = selectableFiles.find((item) => item.fileKey === fileKey);
          if (!target) {
            alert('選択したPDFが見つかりません。再読み込みしてください。');
            return;
          }
          openPdfBtn.disabled = true;
          openPdfBtn.textContent = '取得中...';
          try {
            const blob = await fetchFileBlobByKey(fileKey);
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
            setTimeout(() => URL.revokeObjectURL(url), 60000);
          } catch (err) {
            alert(err && err.message ? err.message : 'PDFの取得に失敗しました');
          } finally {
            openPdfBtn.textContent = 'PDFを開く';
            updateOpenButton();
          }
        };

        footer.appendChild(closeBtn);
        footer.appendChild(openPdfBtn);
        refModal.appendChild(head);
        refModal.appendChild(body);
        refModal.appendChild(footer);
        refOverlay.appendChild(refModal);
        document.body.appendChild(refOverlay);

        loadPdfOptions(toPeriodKey(now.getFullYear(), now.getMonth() + 1));
      }

      payoutCreateButton.onclick = () => openPayoutCreateFromStaffModal();
      payoutReferenceButton.onclick = () => openPayoutReferenceFromStaffModal();

      const roleOptions = ['', 'プレイングマネージャー', '事務', '全体統括'];
      const updateRoleSelectOptions = (selectEl) => {
        if (!selectEl) {
          return;
        }
        const currentValue = String(selectEl.value || role || '').trim();
        const optionSet = new Set(roleOptions.filter((opt) => String(opt || '').trim() !== ''));
        if (currentValue) {
          optionSet.add(currentValue);
        }
        const normalizedOptions = [''].concat(Array.from(optionSet));
        selectEl.innerHTML = '';
        normalizedOptions.forEach((opt) => {
          const option = document.createElement('option');
          option.value = opt;
          option.textContent = opt || '選択してください';
          selectEl.appendChild(option);
        });
        selectEl.value = currentValue;
      };

      const detailItems = [
        { label: 'ID', code: 'id', value: staffId, editable: false },
        { label: '職員名', code: 'name', value: name, editable: true },
        { label: '役職', code: 'role', value: role, editable: true, type: 'select', options: roleOptions },
        { label: '電話番号', code: 'phone', value: phone, editable: true },
        { label: 'メールアドレス', code: 'mail', value: mail, editable: true },
        { label: '備考', code: 'memo', value: memo, editable: true, type: 'textarea' },
      ];

      const detailTable = document.createElement('table');
      detailTable.style.cssText = 'width:100%;border-collapse:collapse;font-size:14px;';
      const editInputs = {};

      detailItems.forEach((item) => {
        const tr = document.createElement('tr');
        tr.style.cssText = 'border-bottom:1px solid #e5e7eb;';

        const th = document.createElement('th');
        th.textContent = item.label;
        th.style.cssText = 'width:180px;padding:10px 8px;text-align:left;color:#374151;background:#f9fafb;vertical-align:top;';

        const td = document.createElement('td');
        td.style.cssText = 'padding:10px 8px;color:#111827;word-break:break-word;';

        if (!item.editable) {
          td.textContent = item.value || '';
        } else if (item.type === 'select') {
          const select = document.createElement('select');
          select.style.cssText = 'width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';
          (item.options || []).forEach((opt) => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt || '選択してください';
            select.appendChild(option);
          });
          select.value = item.value || '';
          td.appendChild(select);
          editInputs[item.code] = select;
        } else if (item.type === 'textarea') {
          const textarea = document.createElement('textarea');
          textarea.value = item.value || '';
          textarea.rows = 3;
          textarea.style.cssText = 'width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';
          td.appendChild(textarea);
          editInputs[item.code] = textarea;
        } else {
          const input = document.createElement('input');
          input.type = 'text';
          input.value = item.value || '';
          input.style.cssText = 'width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;';
          td.appendChild(input);
          editInputs[item.code] = input;
        }

        tr.appendChild(th);
        tr.appendChild(td);
        detailTable.appendChild(tr);
      });

      fetchFormFields(CONFIG.apps.vanzai_staff).then((properties) => {
        const roleCode = findFieldCode(
          properties,
          ['role', 'staff_role', 'position', 'job_title'],
          ['役職', '職種', 'ポジション'],
          ''
        ) || 'role';
        const roleProp = properties[roleCode];
        if (roleProp && (roleProp.type === 'DROP_DOWN' || roleProp.type === 'RADIO_BUTTON')) {
          const fetched = Object.keys(roleProp.options || {}).filter((opt) => String(opt || '').trim() !== '');
          if (fetched.length) {
            roleOptions.splice(0, roleOptions.length, '');
            fetched.forEach((option) => roleOptions.push(option));
          }
        }
        updateRoleSelectOptions(editInputs.role);
      }).catch(() => {
        updateRoleSelectOptions(editInputs.role);
      });

      detailBody.appendChild(detailTable);

      const detailFooter = document.createElement('div');
      detailFooter.style.cssText = 'padding:16px 20px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;gap:12px;';

      const saveButton = document.createElement('button');
      saveButton.textContent = '保存';
      saveButton.className = 'kintoneplugin-button-dialog-ok';
      saveButton.style.cssText = 'padding:10px 24px;border:none;border-radius:4px;background:#10b981;color:white;cursor:pointer;font-size:14px;font-weight:600;';
      saveButton.onclick = () => {
        const recordId = record.$id && record.$id.value ? String(record.$id.value) : '';
        if (!recordId) {
          alert('レコードIDが取得できませんでした');
          return;
        }

        const payload = {
          name: { value: editInputs.name ? String(editInputs.name.value || '').trim() : '' },
          role: { value: editInputs.role ? String(editInputs.role.value || '').trim() : '' },
          phone: { value: editInputs.phone ? String(editInputs.phone.value || '').trim() : '' },
          mail: { value: editInputs.mail ? String(editInputs.mail.value || '').trim() : '' },
          memo: { value: editInputs.memo ? String(editInputs.memo.value || '').trim() : '' },
        };

        saveButton.disabled = true;
        saveButton.textContent = '保存中...';
        kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/record.json`, 'PUT', {
          app: CONFIG.apps.vanzai_staff,
          id: recordId,
          record: payload,
        }).then(() => {
          VANZAI_STAFF_CACHE = null;
          showToast('更新しました');
          document.body.style.overflow = '';
          document.body.removeChild(detailOverlay);
          openVanzaiStaffListModal();
        }).catch((err) => {
          alert('保存に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
        }).finally(() => {
          saveButton.disabled = false;
          saveButton.textContent = '保存';
        });
      };
      detailFooter.appendChild(saveButton);

      const detailCloseButton = document.createElement('button');
      detailCloseButton.textContent = '閉じる';
      detailCloseButton.className = 'kintoneplugin-button-dialog-cancel';
      detailCloseButton.style.cssText = 'padding:10px 24px;border:1px solid #d1d5db;border-radius:4px;background:white;cursor:pointer;font-size:14px;';
      detailCloseButton.onclick = () => {
        document.body.style.overflow = '';
        document.body.removeChild(detailOverlay);
      };
      detailFooter.appendChild(detailCloseButton);

      detailModal.appendChild(detailHeader);
      detailModal.appendChild(detailBody);
      detailModal.appendChild(detailFooter);
      detailOverlay.appendChild(detailModal);
      document.body.style.overflow = 'hidden';
      document.body.appendChild(detailOverlay);
    }

    function renderStaffRows() {
      tbody.innerHTML = '';
      const target = sortStaffRecords(staffRecords);
      if (!target.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="padding:20px;text-align:center;color:#6b7280;">職員データがありません</td></tr>';
        return;
      }
      target.forEach((record) => {
        const row = document.createElement('tr');
        row.style.cssText = 'border-bottom:1px solid #e5e7eb;cursor:pointer;';
        row.onmouseenter = () => { row.style.background = '#fef3c7'; };
        row.onmouseleave = () => { row.style.background = 'white'; };
        row.onclick = () => {
          document.body.style.overflow = '';
          document.body.removeChild(overlay);
          openStaffDetailModal(record);
        };

        [getStaffValue(record, 'id'), getStaffValue(record, 'name'), getStaffValue(record, 'role'), getStaffValue(record, 'phone'), getStaffValue(record, 'mail')]
          .forEach((cellValue) => {
            const td = document.createElement('td');
            td.textContent = cellValue;
            td.style.cssText = 'padding:10px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;';
            td.title = cellValue;
            row.appendChild(td);
          });

        tbody.appendChild(row);
      });
    }

    fetchVanzaiStaffs().then((records) => {
      staffRecords = records || [];
      updateStaffHeaderSortIndicators();
      renderStaffRows();
    }).catch((err) => {
      console.error('職員一覧取得エラー:', err);
      tbody.innerHTML = '<tr><td colspan="5" style="padding:20px;text-align:center;color:#ef4444;">データの取得に失敗しました</td></tr>';
    });

    document.body.style.overflow = 'hidden';
    document.body.appendChild(overlay);
  }

  function openModal(kind, titleOverride) {
    const config = CONFIG[kind];
    const appId = CONFIG.apps[kind];

    const openWithFields = (fields, sourceToCode) => {
      const overlay = buildModal(
        titleOverride || '登録',
        fields,
        (inputs, modal) => {
          try {
            if (kind === 'suppliers') {
              const supplierError = validateSuppliersForm(modal, inputs, sourceToCode);
              if (supplierError) {
                throw new Error(supplierError);
              }
            }
            const record = buildRecord(fields, inputs);
            kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/record.json`, 'POST', {
              app: appId,
              record
            }).then(() => {
              showToast('登録しました');
              document.body.style.overflow = '';
              document.body.removeChild(modal);
              location.reload();
            }).catch((err) => {
              console.error('[ERROR createRecord] appId:', appId);
              console.error('[ERROR createRecord] record keys:', Object.keys(record || {}));
              console.error('[ERROR createRecord] details:', err);
              console.error('[ERROR createRecord] message:', err && err.message ? err.message : 'unknown');
              console.error('[ERROR createRecord] response:', JSON.stringify(err));
              alert('登録に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
            });
          } catch (e) {
            alert(e.message);
          }
        }
      );

      if (config.autoId) {
        const autoFieldCode = sourceToCode && sourceToCode[config.autoId.field]
          ? sourceToCode[config.autoId.field]
          : config.autoId.field;
        const autoInput = overlay.querySelector(`[data-code="${autoFieldCode}"]`);
        if (autoInput) {
          const yearSuffix = String(new Date().getFullYear()).slice(-2);
          const prefix = config.autoId.includeYear
            ? `${config.autoId.prefix}${yearSuffix}`
            : config.autoId.prefix;
          autoInput.readOnly = true;
          autoInput.disabled = true;
          autoInput.value = '採番中...';
          autoInput.style.background = '#f3f4f6';
          autoInput.style.color = '#6b7280';
          autoInput.style.cursor = 'not-allowed';
          fetchNextId(appId, autoFieldCode, prefix, config.autoId.width)
            .then((nextId) => {
              autoInput.value = nextId;
            });
        }
      }

      if (kind === 'projects') {
        setupProjectForm(overlay);
      }
      if (kind === 'workers') {
        setupWorkersForm(overlay, sourceToCode);
      }
      if (kind === 'suppliers') {
        setupSuppliersForm(overlay, sourceToCode);
      }
      if (kind === 'sites') {
        setupSitesForm(overlay, sourceToCode);
      }
      if (kind === 'staff_managers') {
        setupStaffManagersForm(overlay, sourceToCode);
      }
      if (kind === 'project_assignments' && sourceToCode) {
        setupCategoryCascade(overlay, {
          major: sourceToCode.category_major,
          middle: sourceToCode.category_middle,
          minor: sourceToCode.category_minor
        });
        setupProjectAssignmentsForm(overlay, sourceToCode);
      }
      if (kind === 'actuals') {
        const map = sourceToCode || {
          assignment_id: 'assignment_id',
          worker_id: 'worker_id',
          worked_start_time: 'worked_start_time',
          worked_end_time: 'worked_end_time',
          sales_count: 'sales_count',
          memo: 'memo'
        };
        setupActualsForm(overlay, map);
      }

      document.body.style.overflow = 'hidden';
      document.body.appendChild(overlay);
    };

    if (config.resolveByLabelFlexible) {
      resolveFieldsByLabelFlexible(appId, config.fields).then(({ resolvedFields, sourceToCode }) => {
        openWithFields(resolvedFields, sourceToCode);
      }).catch((err) => {
        alert('フォーム情報の取得に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
      });
      return;
    }

    if (config.fieldCodes) {
      const resolvedFields = {};
      const sourceToCode = {};
      const missing = [];
      Object.keys(config.fields).forEach((key) => {
        const meta = config.fields[key];
        const code = config.fieldCodes[key];
        if (!code) {
          missing.push(meta.label || key);
          return;
        }
        resolvedFields[code] = Object.assign({}, meta, { sourceKey: key });
        sourceToCode[key] = code;
      });
      if (missing.length > 0) {
        console.warn('未設定のフィールドコード:', missing);
      }
      openWithFields(resolvedFields, sourceToCode);
      return;
    }

    if (config.resolveByLabel) {
      resolveFieldsByLabel(appId, config.fields).then(({ resolvedFields, sourceToCode }) => {
        openWithFields(resolvedFields, sourceToCode);
      }).catch((err) => {
        alert('フォーム情報の取得に失敗しました: ' + (err && err.message ? err.message : 'unknown'));
      });
      return;
    }

    openWithFields(config.fields);
  }

  function setupStaffManagersForm(overlay, sourceToCode) {
    if (!overlay) {
      return;
    }
    const clientCompanyCode = sourceToCode && sourceToCode.client_company
      ? sourceToCode.client_company
      : 'client_company';
    const clientCompanyInput = overlay.querySelector(`[data-code="${clientCompanyCode}"]`);
    
    if (clientCompanyInput && (clientCompanyInput.tagName === 'SELECT' || clientCompanyInput.tagName === 'INPUT')) {
      fetchClients().then((clientRecords) => {
        console.log('[DEBUG] App167から取得したクライアント数:', clientRecords.length);
        console.log('[DEBUG] クライアントデータ:', clientRecords);

        if (clientCompanyInput.tagName === 'SELECT') {
          clientCompanyInput.innerHTML = '';
          const emptyOption = document.createElement('option');
          emptyOption.value = '';
          emptyOption.textContent = '-- 選択してください --';
          clientCompanyInput.appendChild(emptyOption);
        }

        let dataList = null;
        if (clientCompanyInput.tagName === 'INPUT') {
          const listId = `client-company-list-${clientCompanyCode}`;
          dataList = document.getElementById(listId);
          if (!dataList) {
            dataList = document.createElement('datalist');
            dataList.id = listId;
            document.body.appendChild(dataList);
          }
          dataList.innerHTML = '';
          clientCompanyInput.setAttribute('list', listId);
        }
        
        clientRecords.forEach((client) => {
          const clientName = client.client_name && client.client_name.value ? String(client.client_name.value) : '';
          console.log('[DEBUG] client_name:', clientName);
          if (clientName) {
            const option = document.createElement('option');
            option.value = clientName;
            option.textContent = clientName;
            if (clientCompanyInput.tagName === 'SELECT') {
              clientCompanyInput.appendChild(option);
            } else if (dataList) {
              dataList.appendChild(option);
            }
          }
        });

        if (clientCompanyInput.tagName === 'SELECT') {
          console.log('[DEBUG] ドロップダウンに追加された選択肢数:', clientCompanyInput.options.length - 1);
        } else if (dataList) {
          console.log('[DEBUG] datalistに追加された選択肢数:', dataList.options.length);
        }
      }).catch((err) => {
        console.error('クライアントマスタの取得に失敗:', err);
      });
    }
  }

  function setupWorkersForm(overlay, sourceToCode) {
    if (!overlay) {
      return;
    }
    const idInput = overlay.querySelector('[data-code="worker_id"]');
    const viaCode = sourceToCode && sourceToCode.via_destination
      ? sourceToCode.via_destination
      : 'via_destination';
    const introducerCode = sourceToCode && sourceToCode.introducer_supplier
      ? sourceToCode.introducer_supplier
      : 'introducer_supplier';
    const viaInput = overlay.querySelector(`[data-code="${viaCode}"]`);
    const introducerInput = overlay.querySelector(`[data-code="${introducerCode}"]`) || overlay.querySelector('[data-code="introducer_supplier"]');

    if (idInput) {
      idInput.readOnly = true;
      idInput.disabled = true;
      idInput.style.background = '#f3f4f6';
      idInput.style.color = '#6b7280';
      idInput.style.cursor = 'not-allowed';
    }

    const refreshId = () => {
      if (!idInput) {
        return;
      }
      idInput.value = '採番中...';
      fetchNextId(CONFIG.apps.workers, 'worker_id', 'WRK', 4).then((nextId) => {
        idInput.value = nextId;
      });
    };
    refreshId();

    if (viaInput && viaInput.tagName === 'SELECT') {
      applySelectOptions(viaInput, ['', '下請け', '紹介', 'VANZAI直接']);
    }

    const syncIntroducerByVia = () => {
      if (!introducerInput) {
        return;
      }
      const viaValue = viaInput ? String(viaInput.value || '').trim() : '';
      const isDirect = viaValue === 'VANZAI直接';
      if (isDirect) {
        introducerInput.value = '';
      }
      introducerInput.disabled = isDirect;
      introducerInput.style.background = isDirect ? '#f3f4f6' : 'white';
      introducerInput.style.color = isDirect ? '#6b7280' : '#111827';
      introducerInput.style.cursor = isDirect ? 'not-allowed' : 'text';
    };

    if (viaInput) {
      viaInput.addEventListener('change', syncIntroducerByVia);
    }
    syncIntroducerByVia();
  }

  function setupSuppliersForm(overlay, sourceToCode) {
    if (!overlay || !sourceToCode) {
      return;
    }

    const partnerCategoryCode = sourceToCode.partner_category || null;
    const partnerEntityCode = sourceToCode.partner_entity || null;
    const zipcodeCode = sourceToCode.zipcode || 'zipcode';
    const prefCode = sourceToCode.pref || 'pref';
    const cityEtcCode = sourceToCode.city_etc || 'city_etc';
    const branchNoCode = sourceToCode.bank_branch_number || 'bank_branch_number';
    const holderKanaCode = sourceToCode.bank_account_holder_kana || 'bank_account_holder_kana';
    const statusCode = sourceToCode.invoice_registration_status || 'invoice_registration_status';
    const numberCode = sourceToCode.invoice_registration_number || 'invoice_registration_number';

    const companyNameCode = sourceToCode.company_name || 'company_name';
    const companyKanaCode = sourceToCode.company_name_furigana || 'company_name_furigana';
    const phoneCode = sourceToCode.phone || 'phone';
    const emailCode = sourceToCode.email || 'email';

    const formGrid = overlay.querySelector('.vanzai-form-grid');
    const firstRow = formGrid ? formGrid.querySelector('.vanzai-form-row') : null;

    const categoryRow = partnerCategoryCode
      ? overlay.querySelector(`.vanzai-form-row[data-field-code="${partnerCategoryCode}"]`)
      : null;
    const entityRow = partnerEntityCode
      ? overlay.querySelector(`.vanzai-form-row[data-field-code="${partnerEntityCode}"]`)
      : null;

    const companyNameRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${companyNameCode}"]`);
    const companyKanaRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${companyKanaCode}"]`);
    const phoneRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${phoneCode}"]`);
    const emailRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${emailCode}"]`);

    const zipcodeInput = overlay.querySelector(`[data-code="${zipcodeCode}"]`);
    const prefInput = overlay.querySelector(`[data-code="${prefCode}"]`);
    const cityEtcInput = overlay.querySelector(`[data-code="${cityEtcCode}"]`);
    const companyNameInput = overlay.querySelector(`[data-code="${companyNameCode}"]`);
    const categoryInput = partnerCategoryCode ? overlay.querySelector(`[data-code="${partnerCategoryCode}"]`) : null;
    const entityInput = partnerEntityCode ? overlay.querySelector(`[data-code="${partnerEntityCode}"]`) : null;
    const statusInput = overlay.querySelector(`[data-code="${statusCode}"]`);
    const numberInput = overlay.querySelector(`[data-code="${numberCode}"]`);

    const prefRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${prefCode}"]`);
    const cityEtcRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${cityEtcCode}"]`);
    const branchNoRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${branchNoCode}"]`);
    const holderKanaRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${holderKanaCode}"]`);
    const numberRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${numberCode}"]`);

    const createControlRow = (labelText, options, mark) => {
      const row = document.createElement('div');
      row.className = 'vanzai-form-row half';
      row.dataset.supplierControl = mark;

      const label = document.createElement('label');
      label.textContent = `${labelText} *`;
      label.style.display = 'block';
      label.style.fontSize = '12px';
      label.style.marginBottom = '6px';
      label.style.color = '#374151';

      const select = document.createElement('select');
      select.style.width = '100%';
      select.style.padding = '10px 12px';
      select.style.border = '2px solid #e5e7eb';
      select.style.borderRadius = '8px';
      select.style.background = 'white';
      select.style.boxSizing = 'border-box';
      select.style.fontSize = '14px';
      applySelectOptions(select, options);
      select.dataset[mark] = '1';

      row.appendChild(label);
      row.appendChild(select);
      return { row, select };
    };

    const ensureTopSelectionControls = () => {
      let actualCategoryInput = categoryInput;
      let actualEntityInput = entityInput;

      if (actualCategoryInput && categoryRow && firstRow && formGrid) {
        categoryRow.classList.add('half');
        formGrid.insertBefore(categoryRow, firstRow);
        actualCategoryInput.dataset.supplierKind = '1';
      }
      if (actualEntityInput && entityRow && firstRow && formGrid) {
        entityRow.classList.add('half');
        formGrid.insertBefore(entityRow, firstRow);
        actualEntityInput.dataset.supplierEntity = '1';
      }

      if (!actualCategoryInput && formGrid && firstRow) {
        const generated = createControlRow('区分（紹介者/下請け）', ['', '紹介者', '下請け'], 'supplierKind');
        formGrid.insertBefore(generated.row, firstRow);
        actualCategoryInput = generated.select;
      }
      if (!actualEntityInput && formGrid && firstRow) {
        const generated = createControlRow('法人/個人区分', ['', '企業', '個人'], 'supplierEntity');
        formGrid.insertBefore(generated.row, firstRow);
        actualEntityInput = generated.select;
      }

      return { actualCategoryInput, actualEntityInput };
    };

    const controls = ensureTopSelectionControls();

    [prefRow, cityEtcRow, branchNoRow, holderKanaRow, phoneRow, emailRow].forEach((row) => {
      if (row) {
        row.classList.add('half');
      }
    });

    const syncCompanyRows = () => {
      const selected = controls.actualEntityInput ? String(controls.actualEntityInput.value || '').trim() : '';
      const isCorporate = selected === '企業' || selected === '法人';
      [companyNameRow, companyKanaRow].forEach((row) => {
        if (!row) {
          return;
        }
        row.classList.toggle('hidden', !isCorporate);
      });
      if (!isCorporate) {
        if (companyNameInput) {
          companyNameInput.value = '';
        }
        const companyKanaInput = overlay.querySelector(`[data-code="${companyKanaCode}"]`);
        if (companyKanaInput) {
          companyKanaInput.value = '';
        }
      }
    };
    if (controls.actualEntityInput) {
      controls.actualEntityInput.addEventListener('change', syncCompanyRows);
      controls.actualEntityInput.addEventListener('input', syncCompanyRows);
    }
    syncCompanyRows();

    bindPostalAutoFillToParts(zipcodeInput, prefInput, cityEtcInput);

    [prefInput, cityEtcInput].forEach((input) => {
      if (!input) {
        return;
      }
      input.readOnly = true;
      input.disabled = true;
      input.style.background = '#f3f4f6';
      input.style.color = '#6b7280';
      input.style.cursor = 'not-allowed';
    });

    if (zipcodeInput) {
      const zipcodeRow = overlay.querySelector(`.vanzai-form-row[data-field-code="${zipcodeCode}"]`);
      if (zipcodeRow && !zipcodeRow.querySelector('[data-zip-note="1"]')) {
        const note = document.createElement('div');
        note.dataset.zipNote = '1';
        note.textContent = '※都道府県・市区町村以下は郵便番号から自動入力されるため直接入力できません';
        note.style.marginTop = '6px';
        note.style.fontSize = '11px';
        note.style.color = '#6b7280';
        zipcodeRow.appendChild(note);
      }
    }

    if (statusInput && statusInput.tagName === 'SELECT') {
      const values = Array.from(statusInput.options)
        .map((option) => String(option.value || '').trim())
        .filter((value, index, array) => value && array.indexOf(value) === index);
      applySelectOptions(statusInput, [''].concat(values));
      statusInput.value = '';
    }

    const syncInvoiceNumberVisibility = () => {
      if (!statusInput || !numberRow) {
        return;
      }
      const statusValue = String(statusInput.value || '').trim();
      const isAcquired = statusValue.includes('取得済');
      numberRow.classList.remove('hidden');
      if (!numberInput) {
        return;
      }
      if (isAcquired) {
        numberInput.disabled = false;
        numberInput.readOnly = false;
        numberInput.style.background = '#fff';
        numberInput.style.color = '#111827';
        numberInput.style.cursor = 'text';
      } else {
        numberInput.value = '';
        numberInput.disabled = true;
        numberInput.readOnly = true;
        numberInput.style.background = '#f3f4f6';
        numberInput.style.color = '#6b7280';
        numberInput.style.cursor = 'not-allowed';
        dispatchInputEvents(numberInput);
      }
    };

    if (statusInput) {
      statusInput.addEventListener('input', syncInvoiceNumberVisibility);
      statusInput.addEventListener('change', syncInvoiceNumberVisibility);
    }
    syncInvoiceNumberVisibility();
  }

  function validateSuppliersForm(overlay, inputs, sourceToCode) {
    if (!overlay) {
      return '';
    }
    const kindInput = overlay.querySelector('[data-supplier-kind="1"]');
    const entityInput = overlay.querySelector('[data-supplier-entity="1"]');

    if (!kindInput || !String(kindInput.value || '').trim()) {
      return '区分（紹介者/下請け）を選択してください';
    }
    if (!entityInput || !String(entityInput.value || '').trim()) {
      return '法人/個人区分を選択してください';
    }

    const entity = String(entityInput.value || '').trim();
    const companyCode = sourceToCode && sourceToCode.company_name ? sourceToCode.company_name : 'company_name';
    const companyInput = inputs && inputs[companyCode] ? inputs[companyCode] : overlay.querySelector(`[data-code="${companyCode}"]`);
    if ((entity === '企業' || entity === '法人') && (!companyInput || !String(companyInput.value || '').trim())) {
      return '企業の場合は会社名を入力してください';
    }

    const statusCode = sourceToCode && sourceToCode.invoice_registration_status ? sourceToCode.invoice_registration_status : 'invoice_registration_status';
    const numberCode = sourceToCode && sourceToCode.invoice_registration_number ? sourceToCode.invoice_registration_number : 'invoice_registration_number';
    const statusInput = inputs && inputs[statusCode] ? inputs[statusCode] : overlay.querySelector(`[data-code="${statusCode}"]`);
    const numberInput = inputs && inputs[numberCode] ? inputs[numberCode] : overlay.querySelector(`[data-code="${numberCode}"]`);
    const statusValue = statusInput ? String(statusInput.value || '').trim() : '';
    if (statusValue.includes('取得済') && (!numberInput || !String(numberInput.value || '').trim())) {
      return '適格請求書発行事業者の登録番号を入力してください';
    }

    return '';
  }

  function setupActualsForm(overlay, sourceToCode) {
    if (!overlay || !sourceToCode) {
      return;
    }
    const assignmentSelect = overlay.querySelector(`[data-code="${sourceToCode.assignment_id}"]`);
    const workerSelect = overlay.querySelector(`[data-code="${sourceToCode.worker_id}"]`);
    const salesCountInput = overlay.querySelector(`[data-code="${sourceToCode.sales_count}"]`);
    const salesCountRow = salesCountInput ? salesCountInput.closest('.vanzai-form-row') : null;

    const setSalesVisible = (visible) => {
      if (!salesCountRow) {
        return;
      }
      if (visible) {
        salesCountRow.classList.remove('hidden');
      } else {
        salesCountRow.classList.add('hidden');
        if (salesCountInput) {
          salesCountInput.value = '';
        }
      }
    };

    if (salesCountRow) {
      setSalesVisible(false);
    }

    if (workerSelect) {
      fetchWorkers().then((records) => {
        workerSelect.innerHTML = '';
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '選択してください';
        workerSelect.appendChild(emptyOption);
        records.forEach((r) => {
          const wid = r.worker_id && r.worker_id.value ? String(r.worker_id.value) : '';
          const name = getWorkerDisplayName(r);
          if (!wid) {
            return;
          }
          const opt = document.createElement('option');
          opt.value = wid;
          opt.textContent = name ? `${wid} ${name}` : wid;
          workerSelect.appendChild(opt);
        });
      });
    }

    if (assignmentSelect) {
      fetchAssignmentList().then((records) => {
        assignmentSelect.innerHTML = '';
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '選択してください';
        assignmentSelect.appendChild(emptyOption);

        const recordMap = {};
        records.forEach((r) => {
          const aid = r.assignment_id && r.assignment_id.value ? String(r.assignment_id.value) : '';
          const title = r.assignment_title && r.assignment_title.value ? String(r.assignment_title.value) : '';
          const dateValue = r.start_date && r.start_date.value ? String(r.start_date.value) : '';
          if (!aid) {
            return;
          }
          recordMap[aid] = r;
          const opt = document.createElement('option');
          opt.value = aid;
          opt.textContent = [aid, title, dateValue].filter(Boolean).join(' / ');
          assignmentSelect.appendChild(opt);
        });

        assignmentSelect.addEventListener('change', () => {
          const selected = recordMap[assignmentSelect.value];
          if (!selected) {
            setSalesVisible(false);
            return;
          }
          const salesFlag = selected.sales_flag && selected.sales_flag.value ? String(selected.sales_flag.value) : '';
          setSalesVisible(salesFlag === 'あり');
        });
      });
    }
  }

  function setupProjectAssignmentsForm(overlay, sourceToCode) {
    if (!overlay || !sourceToCode) {
      return;
    }

    const companyNameInput = overlay.querySelector(`[data-code="${sourceToCode.company_name}"]`);
    const startDateInput = overlay.querySelector(`[data-code="${sourceToCode.start_date}"]`);
    const endDateInput = overlay.querySelector(`[data-code="${sourceToCode.end_date}"]`);
    const addressInput = overlay.querySelector(`[data-code="${sourceToCode.address}"]`);
    const titleInput = overlay.querySelector(`[data-code="${sourceToCode.assignment_title}"]`);
    const facilityInput = overlay.querySelector(`[data-code="${sourceToCode.facility_name}"]`);
    const eventInput = overlay.querySelector(`[data-code="${sourceToCode.event_name}"]`);
    const minorSelect = overlay.querySelector(`[data-code="${sourceToCode.category_minor}"]`);
    const headcountRequiredInput = overlay.querySelector(`[data-code="${sourceToCode.billing_rate_monthly}"]`);
    const headcountDirectorInput = overlay.querySelector(`[data-code="${sourceToCode.headcount_director}"]`);
    const headcountStaffInput = overlay.querySelector(`[data-code="${sourceToCode.headcount_staff}"]`);
    const ownerNameInput = overlay.querySelector(`[data-code="${sourceToCode.owner_name}"]`);
    const mainStaffInput = overlay.querySelector(`[data-code="${sourceToCode.main_staff}"]`);
    const playingManagerInput = overlay.querySelector(`[data-code="${sourceToCode.playing_manager}"]`);

    const staffByClient = {};

    Promise.all([fetchClients(), fetchStaffManagers()]).then(([clientRecords, staffRecords]) => {
      console.log('[DEBUG 案件登録] App167から取得したクライアント数:', clientRecords.length);
      console.log('[DEBUG 案件登録] App309から取得した職員数:', staffRecords.length);
      
      clientRecords.forEach((client) => {
        const clientId = client.client_id && client.client_id.value ? String(client.client_id.value) : '';
        const clientName = client.client_name && client.client_name.value ? String(client.client_name.value) : '';
        console.log('[DEBUG 案件登録] client_name:', clientName);
        if (!clientName) {
          return;
        }
        staffByClient[clientName] = [];
      });

      staffRecords.forEach((staff) => {
        const clientCompany = staff.client_company && staff.client_company.value ? String(staff.client_company.value) : '';
        const staffName = staff.name && staff.name.value ? String(staff.name.value) : '';
        console.log('[DEBUG 案件登録] 職員:', staffName, '所属:', clientCompany);
        if (clientCompany && staffName && staffByClient[clientCompany]) {
          staffByClient[clientCompany].push(staffName);
        }
      });
      
      console.log('[DEBUG 案件登録] staffByClientマップ:', staffByClient);

      if (companyNameInput && companyNameInput.tagName === 'SELECT') {
        companyNameInput.innerHTML = '';
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '-- 選択してください --';
        companyNameInput.appendChild(emptyOption);
        Object.keys(staffByClient).forEach((clientName) => {
          const option = document.createElement('option');
          option.value = clientName;
          option.textContent = clientName;
          companyNameInput.appendChild(option);
        });

        companyNameInput.addEventListener('change', () => {
          const selectedClient = companyNameInput.value;
          const staffList = staffByClient[selectedClient] || [];

          if (ownerNameInput && ownerNameInput.tagName === 'SELECT') {
            ownerNameInput.innerHTML = '';
            const emptyOption = document.createElement('option');
            emptyOption.value = '';
            emptyOption.textContent = '-- 選択してください --';
            ownerNameInput.appendChild(emptyOption);
            staffList.forEach((name) => {
              const option = document.createElement('option');
              option.value = name;
              option.textContent = name;
              ownerNameInput.appendChild(option);
            });
          }

          if (mainStaffInput && mainStaffInput.tagName === 'SELECT') {
            mainStaffInput.innerHTML = '';
            const emptyOption = document.createElement('option');
            emptyOption.value = '';
            emptyOption.textContent = '-- 選択してください --';
            mainStaffInput.appendChild(emptyOption);
            staffList.forEach((name) => {
              const option = document.createElement('option');
              option.value = name;
              option.textContent = name;
              mainStaffInput.appendChild(option);
            });
          }
        });
      }
    }).catch((err) => {
      console.error('クライアント・職員マスタの取得に失敗:', err);
    });

    if (playingManagerInput && playingManagerInput.tagName === 'SELECT') {
      fetchVanzaiStaffs().then((staffRecords) => {
        const current = playingManagerInput.value || '';
        playingManagerInput.innerHTML = '';
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = '-- 選択してください --';
        playingManagerInput.appendChild(emptyOption);

        (staffRecords || []).forEach((record) => {
          const staffId = record.id && record.id.value ? String(record.id.value).trim() : '';
          const staffName = record.name && record.name.value ? String(record.name.value).trim() : '';
          if (!staffId) {
            return;
          }
          const option = document.createElement('option');
          option.value = staffId;
          option.textContent = staffName ? `${staffId} ${staffName}` : staffId;
          playingManagerInput.appendChild(option);
        });

        if (current) {
          const exists = Array.from(playingManagerInput.options).some((opt) => opt.value === current);
          if (!exists) {
            const option = document.createElement('option');
            option.value = current;
            option.textContent = current;
            playingManagerInput.appendChild(option);
          }
          playingManagerInput.value = current;
        }
      }).catch((err) => {
        console.error('プレイングマネージャー候補の取得に失敗:', err);
      });
    }

    const timeInputs = [
      overlay.querySelector(`[data-code="${sourceToCode.gathering_time}"]`),
      overlay.querySelector(`[data-code="${sourceToCode.start_time}"]`),
      overlay.querySelector(`[data-code="${sourceToCode.end_time}"]`),
      overlay.querySelector(`[data-code="${sourceToCode.dismissal_time}"]`)
    ].filter(Boolean);

    timeInputs.forEach((input) => {
      bindTimeAutoFormat(input);
    });

    if (startDateInput && endDateInput) {
      const syncEndDate = () => {
        if (!endDateInput.value && startDateInput.value) {
          endDateInput.value = startDateInput.value;
        }
      };
      startDateInput.addEventListener('change', syncEndDate);
      endDateInput.addEventListener('focus', syncEndDate);
      endDateInput.addEventListener('click', syncEndDate);
    }

    if (titleInput) {
      titleInput.readOnly = true;
      titleInput.disabled = true;
      titleInput.style.background = '#f3f4f6';
      titleInput.style.color = '#6b7280';
      titleInput.style.cursor = 'not-allowed';
    }

    if (headcountStaffInput) {
      headcountStaffInput.readOnly = true;
      headcountStaffInput.disabled = true;
      headcountStaffInput.style.background = '#f3f4f6';
      headcountStaffInput.style.color = '#6b7280';
      headcountStaffInput.style.cursor = 'not-allowed';
    }

    const updateTitle = () => {
      if (!titleInput) {
        return;
      }
      const dateValue = startDateInput ? startDateInput.value : '';
      const minorValue = minorSelect ? minorSelect.value.trim() : '';
      const facilityValue = facilityInput ? facilityInput.value.trim() : '';
      const eventValue = eventInput ? eventInput.value.trim() : '';
      const parts = [dateValue, minorValue, facilityValue, eventValue].filter(Boolean);
      titleInput.value = parts.join(' ');
      dispatchInputEvents(titleInput);
    };

    if (startDateInput) {
      startDateInput.addEventListener('change', updateTitle);
      startDateInput.addEventListener('input', updateTitle);
    }
    if (minorSelect) {
      minorSelect.addEventListener('change', updateTitle);
    }
    if (facilityInput) {
      facilityInput.addEventListener('input', updateTitle);
      facilityInput.addEventListener('change', updateTitle);
    }
    if (eventInput) {
      eventInput.addEventListener('input', updateTitle);
      eventInput.addEventListener('change', updateTitle);
    }

    const updateHeadcountStaff = () => {
      if (!headcountStaffInput) {
        return;
      }
      const requiredValue = headcountRequiredInput ? Number(headcountRequiredInput.value) : 0;
      const directorValue = headcountDirectorInput ? Number(headcountDirectorInput.value) : 0;
      if (!Number.isFinite(requiredValue) || !Number.isFinite(directorValue)) {
        return;
      }
      const staffValue = Math.max(0, requiredValue - directorValue);
      headcountStaffInput.value = staffValue ? String(staffValue) : '';
      dispatchInputEvents(headcountStaffInput);
    };

    if (headcountRequiredInput) {
      headcountRequiredInput.addEventListener('input', updateHeadcountStaff);
      headcountRequiredInput.addEventListener('change', updateHeadcountStaff);
    }
    if (headcountDirectorInput) {
      headcountDirectorInput.addEventListener('input', updateHeadcountStaff);
      headcountDirectorInput.addEventListener('change', updateHeadcountStaff);
    }

    updateTitle();
    updateHeadcountStaff();
  }

  function formatWeekdayRange(startDate, endDate) {
    if (!startDate) {
      return '';
    }
    const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
    const startLabel = weekdays[startDate.getDay()];
    if (!endDate || endDate.getTime() === startDate.getTime()) {
      return startLabel;
    }
    const endLabel = weekdays[endDate.getDay()];
    return `${startLabel}〜${endLabel}`;
  }

  function parseDateValue(value) {
    if (!value) {
      return null;
    }
    const date = new Date(value + 'T00:00:00');
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function parseTimeValue(value) {
    if (!value) {
      return null;
    }
    const [h, m] = value.split(':').map((v) => Number(v));
    if (Number.isNaN(h) || Number.isNaN(m)) {
      return null;
    }
    return h * 60 + m;
  }

  function calcHours(startMinutes, endMinutes) {
    if (startMinutes == null || endMinutes == null) {
      return '';
    }
    let diff = endMinutes - startMinutes;
    if (diff < 0) {
      diff += 24 * 60;
    }
    const hours = diff / 60;
    return Number.isFinite(hours) ? hours.toFixed(2).replace(/\.00$/, '') : '';
  }

  function setupProjectForm(overlay) {
    const nameInput = overlay.querySelector('[data-code="name"]');
    const majorSelect = overlay.querySelector('[data-code="project_category_major"]');
    const middleSelect = overlay.querySelector('[data-code="project_category_middle"]');
    const minorSelect = overlay.querySelector('[data-code="project_category_minor"]');
    const typeInput = overlay.querySelector('[data-code="request_project_type"]');

    // カテゴリマスタをロードしてselect初期化
    loadCategoryData().then(() => {
      initCategorySelects(majorSelect, middleSelect, minorSelect);
    }).catch((err) => {
      console.error('カテゴリマスタ読み込みエラー:', err);
    });
    const facilityInput = overlay.querySelector('[data-code="request_facility"]');
    const eventInput = overlay.querySelector('[data-code="request_event_name"]');
    const dateInput = overlay.querySelector('[data-code="request_date"]');
    const endDateInput = overlay.querySelector('[data-code="request_end_date"]');
    const weekdayInput = overlay.querySelector('[data-code="request_weekday"]');
    const startTimeInput = overlay.querySelector('[data-code="work_start_time"]');
    const endTimeInput = overlay.querySelector('[data-code="work_end_time"]');
    const hoursInput = overlay.querySelector('[data-code="work_hours"]');
    const endDateRow = overlay.querySelector('[data-field-code="request_end_date"]');

    if (weekdayInput) {
      weekdayInput.readOnly = true;
      weekdayInput.disabled = true;
      weekdayInput.style.background = '#f3f4f6';
      weekdayInput.style.color = '#6b7280';
      weekdayInput.style.cursor = 'not-allowed';
    }

    const toggleWrapper = document.createElement('div');
    toggleWrapper.className = 'vanzai-form-row';
    const toggleLabel = document.createElement('label');
    toggleLabel.style.display = 'flex';
    toggleLabel.style.alignItems = 'center';
    toggleLabel.style.gap = '8px';
    toggleLabel.style.fontSize = '13px';
    toggleLabel.style.color = '#374151';
    const toggleInput = document.createElement('input');
    toggleInput.type = 'checkbox';
    toggleInput.checked = false;
    toggleLabel.appendChild(toggleInput);
    toggleLabel.appendChild(document.createTextNode('複数日（終了日を入力する）'));
    toggleWrapper.appendChild(toggleLabel);

    if (endDateRow) {
      endDateRow.classList.add('hidden');
      endDateRow.parentNode.insertBefore(toggleWrapper, endDateRow);
    }

    if (nameInput) {
      nameInput.readOnly = true;
      nameInput.disabled = true;
      nameInput.style.background = '#f3f4f6';
      nameInput.style.color = '#6b7280';
      nameInput.style.cursor = 'not-allowed';
    }

    if (hoursInput) {
      hoursInput.readOnly = true;
      hoursInput.disabled = true;
      hoursInput.style.background = '#f3f4f6';
      hoursInput.style.color = '#6b7280';
      hoursInput.style.cursor = 'not-allowed';
    }

    const updateName = () => {
      if (!nameInput) {
        return;
      }
      const typeValue = typeInput ? typeInput.value.trim() : '';
      const facilityValue = facilityInput ? facilityInput.value.trim() : '';
      const eventValue = eventInput ? eventInput.value.trim() : '';
      if (!typeValue && !facilityValue && !eventValue) {
        nameInput.value = '';
        return;
      }
      if (facilityValue || eventValue) {
        const middle = [facilityValue, eventValue].filter(Boolean).join('_');
        nameInput.value = middle ? `${typeValue}【${middle}】` : typeValue;
      } else {
        nameInput.value = typeValue;
      }
    };

    const applyOptions = (selectEl, options) => {
      if (!selectEl) {
        return;
      }
      const current = selectEl.value;
      selectEl.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '選択してください';
      selectEl.appendChild(emptyOption);
      (options || []).forEach((opt) => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        selectEl.appendChild(option);
      });
      if (current && options && options.includes(current)) {
        selectEl.value = current;
      }
    };

    const updateMiddleOptions = () => {
      if (!majorSelect || !middleSelect || !CATEGORY_RULES) {
        return;
      }
      const majorValue = majorSelect.value;
      let options = CATEGORY_RULES.majorToMiddle[majorValue] || [];
      if (options.length === 0 && CATEGORY_OPTIONS && CATEGORY_OPTIONS.middle) {
        options = CATEGORY_OPTIONS.middle.filter((value) => value !== '');
      }
      applyOptions(middleSelect, options);
      updateMinorOptions();
    };

    const updateMinorOptions = () => {
      if (!minorSelect || !middleSelect || !CATEGORY_RULES) {
        return;
      }
      const middleValue = middleSelect.value;
      const middleKey = String(middleValue || '').trim().replace(/[：:]/g, '');
      const options = CATEGORY_RULES.middleToMinor[middleKey] || [];
      applyOptions(minorSelect, options);
    };

    const updateWeekday = () => {
      if (!weekdayInput) {
        return;
      }
      const startDate = parseDateValue(dateInput ? dateInput.value : '');
      const endDate = parseDateValue(endDateInput ? endDateInput.value : '');
      weekdayInput.value = formatWeekdayRange(startDate, endDate);
    };

    const updateHours = () => {
      if (!hoursInput) {
        return;
      }
      const startMinutes = parseTimeValue(startTimeInput ? startTimeInput.value : '');
      const endMinutes = parseTimeValue(endTimeInput ? endTimeInput.value : '');
      hoursInput.value = calcHours(startMinutes, endMinutes);
    };

    if (typeInput && typeInput.tagName === 'SELECT') {
      loadProjectTypes(typeInput).then(updateName).catch(() => {});
      typeInput.addEventListener('change', updateName);
    } else if (typeInput) {
      typeInput.addEventListener('input', updateName);
    }
    if (toggleInput && endDateRow) {
      toggleInput.addEventListener('change', () => {
        if (toggleInput.checked) {
          endDateRow.classList.remove('hidden');
        } else {
          endDateRow.classList.add('hidden');
          if (endDateInput) {
            endDateInput.value = '';
          }
        }
        updateWeekday();
      });
    }
    if (facilityInput) {
      facilityInput.addEventListener('input', updateName);
    }
    if (eventInput) {
      eventInput.addEventListener('input', updateName);
    }
    if (dateInput) {
      dateInput.addEventListener('change', updateWeekday);
    }
    if (endDateInput) {
      endDateInput.addEventListener('change', updateWeekday);
    }
    if (startTimeInput) {
      startTimeInput.addEventListener('change', updateHours);
    }
    if (endTimeInput) {
      endTimeInput.addEventListener('change', updateHours);
    }

    if (majorSelect) {
      majorSelect.addEventListener('change', updateMiddleOptions);
    }
    if (middleSelect) {
      middleSelect.addEventListener('change', updateMinorOptions);
    }

    updateMiddleOptions();

    updateName();
    updateWeekday();
    updateHours();
  }

  function loadCategoryData() {
    if (CATEGORY_DATA) {
      return Promise.resolve(CATEGORY_DATA);
    }
    const query = 'order by type_id asc limit 500';
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: CONFIG.apps.project_types,
      query,
      fields: ['name', 'category_level', 'parent_major', 'parent_middle']
    }).then((resp) => {
      const records = resp.records || [];
      const normalizeValue = (value) => String(value || '').trim();
      const normalizeCategoryKey = (value) => normalizeValue(value).replace(/[：:]/g, '');
      const normalizeMiddleOrderKey = (value) => normalizeValue(value).replace(/[\s：:]/g, '');
      const extract巡回Price = (value) => {
        const match = normalizeMiddleOrderKey(value).match(/店巡回(\d+)円/);
        return match ? Number(match[1]) : null;
      };
      CATEGORY_DATA = records.map((record) => ({
        name: normalizeValue(record.name ? record.name.value : ''),
        level: normalizeValue(record.category_level ? record.category_level.value : ''),
        parentMajor: normalizeValue(record.parent_major ? record.parent_major.value : ''),
        parentMiddle: normalizeValue(record.parent_middle ? record.parent_middle.value : '')
      }));

      const sortUnique = (items, comparator) => Array.from(new Set(items.filter(Boolean)))
        .sort(comparator || ((a, b) => a.localeCompare(b, 'ja')));
      const sortMiddle = (items) => sortUnique(items, (a, b) => {
        const aPrice = extract巡回Price(a);
        const bPrice = extract巡回Price(b);
        if (aPrice !== null && bPrice !== null) {
          return bPrice - aPrice;
        }
        return a.localeCompare(b, 'ja');
      });

      // オプション配列を構築
      CATEGORY_OPTIONS = {
        major: [''].concat(sortUnique(CATEGORY_DATA.filter((c) => c.level === 'major').map((c) => c.name))),
        middle: [''].concat(sortMiddle(CATEGORY_DATA.filter((c) => c.level === 'middle').map((c) => c.name))),
        minor: [''].concat(sortUnique(CATEGORY_DATA.filter((c) => c.level === 'minor').map((c) => c.name)))
      };

      // 親子関係のルールを構築
      CATEGORY_RULES = { majorToMiddle: {}, middleToMinor: {} };

      // major -> middle
      CATEGORY_DATA.filter((c) => c.level === 'middle' && c.parentMajor).forEach((c) => {
        const parents = c.parentMajor.split('|').map((value) => normalizeValue(value)).filter(Boolean);
        parents.forEach((parent) => {
          if (!CATEGORY_RULES.majorToMiddle[parent]) {
            CATEGORY_RULES.majorToMiddle[parent] = [];
          }
          CATEGORY_RULES.majorToMiddle[parent].push(c.name);
        });
      });

      // middle -> minor
      CATEGORY_DATA.filter((c) => c.level === 'minor' && c.parentMiddle).forEach((c) => {
        const parentKey = normalizeCategoryKey(c.parentMiddle);
        if (!CATEGORY_RULES.middleToMinor[parentKey]) {
          CATEGORY_RULES.middleToMinor[parentKey] = [];
        }
        CATEGORY_RULES.middleToMinor[parentKey].push(c.name);
      });

      Object.keys(CATEGORY_RULES.majorToMiddle).forEach((key) => {
        CATEGORY_RULES.majorToMiddle[key] = sortMiddle(CATEGORY_RULES.majorToMiddle[key]);
      });
      Object.keys(CATEGORY_RULES.middleToMinor).forEach((key) => {
        CATEGORY_RULES.middleToMinor[key] = sortUnique(CATEGORY_RULES.middleToMinor[key]);
      });

      return CATEGORY_DATA;
    });
  }

  function initCategorySelects(majorSelect, middleSelect, minorSelect) {
    if (!CATEGORY_OPTIONS) {
      return;
    }
    const applyOptions = (selectEl, options, current) => {
      if (!selectEl) {
        return;
      }
      selectEl.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '選択してください';
      selectEl.appendChild(emptyOption);
      (options || []).forEach((opt) => {
        if (opt === '') {
          return;
        }
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        selectEl.appendChild(option);
      });
      if (current && options && options.includes(current)) {
        selectEl.value = current;
      }
    };
    if (majorSelect) {
      applyOptions(majorSelect, CATEGORY_OPTIONS.major);
    }
    if (middleSelect) {
      applyOptions(middleSelect, []);
    }
    if (minorSelect) {
      applyOptions(minorSelect, []);
    }
  }

  function loadProjectTypes(selectEl) {
    const query = 'order by type_id asc';
    return kintone.api(`/k/guest/${GUEST_SPACE_ID}/v1/records.json`, 'GET', {
      app: CONFIG.apps.project_types,
      query,
      fields: ['type_id', 'name']
    }).then((resp) => {
      const records = resp.records || [];
      const options = records.map((record) => {
        const name = record.name ? record.name.value : '';
        return name;
      }).filter((value) => value);

      selectEl.innerHTML = '';
      const emptyOption = document.createElement('option');
      emptyOption.value = '';
      emptyOption.textContent = '選択してください';
      selectEl.appendChild(emptyOption);
      options.forEach((opt) => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        selectEl.appendChild(option);
      });
    });
  }

  function ensureVersionBadge() {
    if (document.getElementById('vanzai-front-version-badge')) {
      return;
    }
    const badge = document.createElement('div');
    badge.id = 'vanzai-front-version-badge';
    badge.className = 'vanzai-front-version-badge';
    badge.textContent = `FD ${FRONT_DASHBOARD_BUILD_MARKER}`;
    document.body.appendChild(badge);
  }

  kintone.events.on('app.record.index.show', function () {
    const space = kintone.app.getHeaderMenuSpaceElement();
    if (!space || space.dataset.frontDashboardReady === '1') {
      return;
    }
    space.dataset.frontDashboardReady = '1';

    console.log('=== VANZAI ダッシュボード初期化 ===');
    console.log('BUILD_MARKER:', FRONT_DASHBOARD_BUILD_MARKER);
    console.log('GUEST_SPACE_ID:', GUEST_SPACE_ID);
    console.log('CONFIG.apps:', CONFIG.apps);
    console.log('現在のアプリID:', kintone.app.getId());
    console.log('================================');

    ensureStyle();
    ensureVersionBadge();

    const createClientRegisterGroup = () => {
      const group = document.createElement('div');
      group.className = 'vanzai-front-client-group';

      const slide = document.createElement('div');
      slide.className = 'vanzai-front-client-slide';
      slide.appendChild(createButton('クライアントを登録', () => openModal('clients', 'クライアント登録'), 'quaternary mini'));
      slide.appendChild(createButton('クライアント職員を登録', () => openModal('staff_managers', 'クライアント職員登録'), 'quaternary mini'));

      const toggleButton = createButton('クライアント', () => {
        slide.classList.toggle('open');
      }, 'quaternary');

      group.appendChild(toggleButton);
      group.appendChild(slide);
      return group;
    };

    const registerRow = createRow('登録');
    registerRow.appendChild(createClientRegisterGroup());
    registerRow.appendChild(createButton('VANZAI職員の登録', () => openModal('vanzai_staff', 'VANZAI職員登録'), 'quaternary'));
    registerRow.appendChild(createButton('紹介者/下請けの登録', () => openModal('suppliers', '紹介者/下請け登録')));
    registerRow.appendChild(createButton('現場を登録', () => openModal('sites', '現場登録'), 'secondary'));
    registerRow.appendChild(createButton('稼働者を登録', () => openModal('workers', '稼働者登録'), 'tertiary'));
    registerRow.appendChild(createButton('案件を登録', () => openModal('project_assignments', '案件登録')));
    space.appendChild(registerRow);

    const viewRow = createRow('確認');
    viewRow.appendChild(createButton('案件確認・稼働者/実績登録', () => openAssignmentListModal(), 'secondary'));
    viewRow.appendChild(createButton('見積/請求書、支払明細書の発行', () => openBillingIssueModal(), 'secondary'));
    viewRow.appendChild(createButton('稼働者一覧', () => openWorkerListModal(), 'secondary'));
    viewRow.appendChild(createButton('職員一覧', () => openVanzaiStaffListModal(), 'secondary'));
    space.appendChild(viewRow);
  });
})();
