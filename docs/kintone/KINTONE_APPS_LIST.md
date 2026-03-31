# Kintone アプリ構成

## アプリ一覧（ID/URL/目的）

**ゲストスペースURL**: https://xtf5wpxp3gk2.cybozu.com/k/guest/3/
**参照CSV**: [kintone_app/アプリ一覧 (VANZAI).csv](../../kintone_app/%E3%82%A2%E3%83%97%E3%83%AA%E4%B8%80%E8%A6%A7%20%28VANZAI%29.csv)

| 区分 | アプリ名（CSV） | アプリコード | App ID | URL | 目的（簡単） |
|---|---|---|---|---|---|
| その他 | project_documents_sjis | project_documents | 144 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/144/ | 案件説明資料 |
| その他 | tasks_sjis | tasks | 145 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/145/ | 案件タスク進捗 |
| その他 | equipment_loans_sjis | equipment_loans | 146 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/146/ | 貸出/返却管理 |
| その他 | equipment_sjis | equipment | 147 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/147/ | 備品種別管理 |
| 請求/支払 | bank_transfer_batches_sjis | bank_transfer_batches | 148 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/148/ | 一括振込管理 |
| 請求/支払 | payout_deliveries_sjis | payout_deliveries | 149 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/149/ | 支払明細送信履歴 |
| 請求/支払 | incentives_sjis | incentives | 150 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/150/ | インセンティブ |
| 請求/支払 | expenses_sjis | expenses | 151 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/151/ | 経費精算 |
| ルール | incentive_rules_sjis | incentive_rules | 152 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/152/ | 条件/金額の管理（重複候補） |
| ルール | task_templates_sjis | task_templates | 153 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/153/ | タスク雛形（重複候補） |
| 単価 | price_rules_sjis | price_rules | 154 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/154/ | ルール単価管理（重複候補） |
| ルール | incentive_rules_sjis | incentive_rules | 155 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/155/ | 条件/金額の管理 |
| ルール | task_templates_sjis | task_templates | 156 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/156/ | タスク雛形 |
| 単価 | price_rules_sjis | price_rules | 157 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/157/ | ルール単価管理 |
| トランザクション | assignments_sjis | assignments | 158 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/158/ | 稼働者割当 |
| トランザクション | shift_slots_sjis | shift_slots | 159 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/159/ | シフト予定 |
| トランザクション | projects_sjis | projects | 160 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/160/ | 案件情報 |
| 単価 | price_outsource_sjis | price_outsource | 161 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/161/ | 外注単価管理 |
| 単価 | price_sales_sjis | price_sales | 162 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/162/ | 売上単価管理 |
| マスタ | roles_sjis | roles | 163 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/163/ | 役割の管理 |
| マスタ | project_types_sjis | project_types | 164 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/164/ | 案件種別の管理 |
| マスタ | workers_sjis | workers | 165 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/165/ | 稼働者の基本情報管理 |
| マスタ | sites_sjis | sites | 166 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/166/ | 稼働現場管理 |
| マスタ | clients_sjis | clients | 167 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/167/ | 請求先管理 |
| トランザクション | actuals_sample_sjis | actuals | 168 | https://xtf5wpxp3gk2.cybozu.com/k/guest/3/168/ | 実績（サンプル/取込） |

### 追加アプリ（運用補助 / App174フロント導線）

以下は「フロント（登録ダッシュボード）」で利用する補助アプリです（ゲストスペース内で作成）。

| 用途 | アプリコード | App ID | 備考 |
|---|---:|---:|---|
| 登録ダッシュボード | front_dashboard | 174 | `kintone_app/customizations/front_dashboard.js` を適用 |
| 案件登録（カテゴリ分け） | project_assignments | 307 | 「案件を登録」「案件確認」の対象 |
| クライアント職員（責任者/担当者等） | staff_managers | 400 | ドロップダウン選択の参照元 |

※ incentive_rules / task_templates / price_rules はCSV内で複数IDが存在します。使用するIDを確定してください。

## 必要なアプリ一覧

### 1️⃣ マスタアプリ（5個）

#### M1. 稼働者マスタ (workers)
- **アプリコード**: `workers`
- **用途**: 稼働者の基本情報管理
- **主要フィールド**:
  - worker_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - email (文字列・一行)
  - phone (文字列・一行)
  - is_active (ドロップダウン: 有効/無効)
  - is_site_manager (ドロップダウン: はい/いいえ) ※現場管理者マーク
  - bank_code (文字列・一行) ※金融機関コード
  - branch_code (文字列・一行) ※支店コード
  - account_type (ドロップダウン: 普通/当座)
  - account_number (文字列・一行) ※口座番号
  - account_holder_kana (文字列・一行) ※口座名義カナ
  - notes (文字列・複数行)

#### M2. クライアントマスタ (clients)
- **アプリコード**: `clients`
- **用途**: 請求先管理
- **主要フィールド**:
  - client_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - code (文字列・一行)
  - address (文字列・複数行)
  - billing_email (文字列・一行)
  - notes (文字列・複数行)

#### M3. 現場マスタ (sites)
- **アプリコード**: `sites`
- **用途**: 稼働現場管理
- **主要フィールド**:
  - site_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - code (文字列・一行)
  - address (文字列・複数行)
  - notes (文字列・複数行)

#### M4. 案件種別マスタ (project_types)
- **アプリコード**: `project_types`
- **用途**: 案件種別（警備、イベント等）
- **主要フィールド**:
  - type_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - description (文字列・複数行)

#### M5. 役割マスタ (roles)
- **アプリコード**: `roles`
- **用途**: 役割（警備員、責任者等）
- **主要フィールド**:
  - role_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - description (文字列・複数行)

---

### 2️⃣ 単価マスタアプリ（3個）

#### P1. 売上単価マスタ (price_sales)
- **アプリコード**: `price_sales`
- **用途**: クライアント向け売上単価
- **主要フィールド**:
  - price_id (文字列・一行, 必須, ユニーク)
  - client_id (文字列・一行)
  - project_id (文字列・一行)
  - role_id (文字列・一行)
  - unit_price (数値, 必須)
  - valid_from (日付)
  - valid_until (日付)
  - is_default (ドロップダウン: はい/いいえ)
  - notes (文字列・複数行)

#### P2. 外注単価マスタ (price_outsource)
- **アプリコード**: `price_outsource`
- **用途**: 稼働者への支払単価
- **主要フィールド**:
  - price_id (文字列・一行, 必須, ユニーク)
  - worker_id (文字列・一行)
  - project_id (文字列・一行)
  - role_id (文字列・一行)
  - unit_price (数値, 必須)
  - valid_from (日付)
  - valid_until (日付)
  - is_default (ドロップダウン: はい/いいえ)
  - notes (文字列・複数行)

#### P3. 単価ルールマスタ (price_rules)
- **アプリコード**: `price_rules`
- **用途**: 条件ベース単価（深夜割増等）
- **主要フィールド**:
  - rule_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - priority (数値)
  - conditions_json (文字列・複数行) ※JSON形式
  - sales_price (数値)
  - outsource_price (数値)
  - valid_from (日付)
  - valid_until (日付)
  - is_active (ドロップダウン: 有効/無効)

---

### 3️⃣ トランザクションアプリ（4個）

#### T1. 案件マスタ (projects)
- **アプリコード**: `projects`
- **用途**: 案件の基本情報
- **主要フィールド**:
  - project_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - client_id (文字列・一行, 必須)
  - site_id (文字列・一行, 必須)
  - project_type_id (文字列・一行, 必須)
  - start_date (日付, 必須)
  - end_date (日付)
  - status (ドロップダウン: operating/completed/canceled)
  - primary_manager_id (文字列・一行) ※主担当現場管理者
  - secondary_manager_id (文字列・一行) ※副担当現場管理者
  - has_incentive (ドロップダウン: はい/いいえ) ※インセンティブ有無
  - notes (文字列・複数行)
  - request_title (文字列・一行) ※案件依頼タイトル
  - request_project_type (文字列・一行) ※案件種別（名称）
  - request_date (日付) ※実施日
  - request_weekday (文字列・一行)
  - request_facility (文字列・一行)
  - request_event_name (文字列・一行)
  - request_address (文字列・複数行)
  - request_content (文字列・複数行)
  - director_count (数値)
  - director_days (数値)
  - staff_count (数値)
  - staff_days (数値)
  - meeting_time (時刻)
  - work_start_time (時刻)
  - work_end_time (時刻)
  - work_hours (数値)
  - dismissal_time (時刻)
  - director_unit_price (数値)
  - staff_unit_price (数値)
  - director_labor_cost (数値)
  - staff_labor_cost (数値)
  - total_labor_cost (数値)

#### T2. シフト枠 (shift_slots)
- **アプリコード**: `shift_slots`
- **用途**: 日別シフト枠
- **主要フィールド**:
  - slot_id (文字列・一行, 必須, ユニーク)
  - project_id (文字列・一行, 必須)
  - work_date (日付, 必須)
  - start_time (時刻, 必須)
  - end_time (時刻, 必須)
  - required_count (数値)
  - site_manager_id (文字列・一行) ※現場管理者
  - notes (文字列・複数行)

#### T3. アサインメント (assignments)
- **アプリコード**: `assignments`
- **用途**: シフト枠への稼働者アサイン
- **主要フィールド**:
  - assignment_id (文字列・一行, 必須, ユニーク)
  - shift_slot_id (文字列・一行, 必須)
  - worker_id (文字列・一行, 必須)
  - role_id (文字列・一行, 必須)
  - status (ドロップダウン: tentative/confirmed/canceled)
  - locked_price_sales (数値)
  - locked_price_outsource (数値)
  - notes (文字列・複数行)

#### T4. 実績CSV取り込み (actuals_import)
- **アプリコード**: `actuals_import`
- **用途**: CSV取り込み履歴と結果
- **主要フィールド**:
  - batch_id (文字列・一行, 必須, ユニーク)
  - file_name (文字列・一行, 必須)
  - project_id (文字列・一行)
  - period_key (文字列・一行) ※YYYYMM
  - mode (ドロップダウン: replace_scope/append)
  - status (ドロップダウン: completed/failed/partial_error)
  - count_success (数値)
  - count_error (数値)
  - submitted_by (文字列・一行)
  - submit_date (日時)
  - errors_json (文字列・複数行)

---

### 4️⃣ 請求・支払アプリ（2個）

#### B1. 請求書 (invoices)
- **アプリコード**: `invoices`
- **用途**: 請求書管理
- **主要フィールド**:
  - invoice_id (文字列・一行, 必須, ユニーク)
  - client_id (文字列・一行, 必須)
  - project_id (文字列・一行)
  - period_key (文字列・一行, 必須) ※YYYYMM
  - billing_date (日付)
  - version (数値)
  - status (ドロップダウン: preparing/issued/superseded)
  - subtotal (数値)
  - tax_amount (数値)
  - total_amount (数値)
  - parent_invoice_id (文字列・一行)
  - superseded_by_id (文字列・一行)

#### B2. 支払明細 (payouts)
- **アプリコード**: `payouts`
- **用途**: 支払明細管理
- **主要フィールド**:
  - payout_id (文字列・一行, 必須, ユニーク)
  - worker_id (文字列・一行, 必須)
  - project_id (文字列・一行)
  - period_key (文字列・一行, 必須) ※YYYYMM
  - payment_date (日付)
  - version (数値)
  - status (ドロップダウン: preparing/confirmed/paid/superseded)
  - total_amount (数値)
  - parent_payout_id (文字列・一行)
  - superseded_by_id (文字列・一行)

#### B3. 経費精算 (expenses)
- **アプリコード**: `expenses`
- **用途**: 経費実費精算管理
- **主要フィールド**:
  - expense_id (文字列・一行, 必須, ユニーク)
  - project_id (文字列・一行, 必須)
  - worker_id (文字列・一行)
  - expense_date (日付, 必須)
  - category (ドロップダウン: 交通費/材料費/その他)
  - amount (数値, 必須)
  - description (文字列・複数行)
  - receipt_file (添付ファイル)
  - status (ドロップダウン: pending/approved/rejected)
  - approved_by (文字列・一行)
  - approved_at (日時)
  - target_invoice_id (文字列・一行)
  - target_payout_id (文字列・一行)

#### B4. インセンティブ (incentives)
- **アプリコード**: `incentives`
- **用途**: インセンティブ支給管理
- **主要フィールド**:
  - incentive_id (文字列・一行, 必須, ユニーク)
  - incentive_rule_id (文字列・一行)
  - worker_id (文字列・一行, 必須)
  - project_id (文字列・一行)
  - period_key (文字列・一行, 必須) ※YYYYMM
  - amount (数値, 必須)
  - reason (文字列・複数行)
  - status (ドロップダウン: pending/approved/paid)
  - approved_by (文字列・一行)
  - approved_at (日時)
  - target_invoice_id (文字列・一行)
  - target_payout_id (文字列・一行)

#### B5. 支払明細送信履歴 (payout_deliveries)
- **アプリコード**: `payout_deliveries`
- **用途**: 支払明細の送信記録
- **主要フィールド**:
  - delivery_id (文字列・一行, 必須, ユニーク)
  - payout_id (文字列・一行, 必須)
  - worker_id (文字列・一行, 必須)
  - delivery_method (ドロップダウン: email/system_notification)
  - recipient_email (文字列・一行)
  - sent_at (日時)
  - status (ドロップダウン: pending/sent/failed/bounced)
  - error_message (文字列・複数行)

#### B6. 銀行振込バッチ (bank_transfer_batches)
- **アプリコード**: `bank_transfer_batches`
- **用途**: 銀行一括振込管理
- **主要フィールド**:
  - batch_id (文字列・一行, 必須, ユニーク)
  - period_key (文字列・一行, 必須) ※YYYYMM
  - format_type (ドロップダウン: zengin_fb/zengin_csv)
  - total_count (数値)
  - total_amount (数値)
  - file_name (文字列・一行)
  - file (添付ファイル)
  - status (ドロップダウン: preparing/exported/uploaded/completed)
  - created_by (文字列・一行)
  - created_at (日時)
  - uploaded_at (日時)
  - completed_at (日時)

---

### 5️⃣ 締め・管理アプリ（5個）

#### C1. 締め管理 (closings)
- **アプリコード**: `closings`
- **用途**: 月次締め状態管理
- **主要フィールド**:
  - closing_id (文字列・一行, 必須, ユニーク)
  - project_id (文字列・一行, 必須)
  - month_key (文字列・一行, 必須) ※YYYYMM
  - status (ドロップダウン: open/soft_closed/hard_closed)
  - closed_by (文字列・一行)
  - closed_at (日時)
  - release_count (数値)
  - release_deadline (日付)
  - notes (文字列・複数行)

#### C2. 貸出備品マスタ (equipment)
- **アプリコード**: `equipment`
- **用途**: 備品種別管理
- **主要フィールド**:
  - equipment_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - category (ドロップダウン: ユニフォーム/無線機/ヘルメット/その他)
  - description (文字列・複数行)
  - total_stock (数値)
  - available_stock (数値)

#### C3. 貸出備品管理 (equipment_loans)
- **アプリコード**: `equipment_loans`
- **用途**: 備品貸出・返却管理
- **主要フィールド**:
  - loan_id (文字列・一行, 必須, ユニーク)
  - equipment_id (文字列・一行, 必須)
  - worker_id (文字列・一行, 必須)
  - project_id (文字列・一行)
  - loan_date (日付, 必須)
  - expected_return_date (日付)
  - actual_return_date (日付)
  - quantity (数値)
  - status (ドロップダウン: loaned/returned/overdue/lost)
  - notes (文字列・複数行)

#### C4. タスク進捗 (tasks)
- **アプリコード**: `tasks`
- **用途**: 案件タスク進捗管理
- **主要フィールド**:
  - task_id (文字列・一行, 必須, ユニーク)
  - project_id (文字列・一行, 必須)
  - task_template_id (文字列・一行)
  - title (文字列・一行, 必須)
  - description (文字列・複数行)
  - assignee_id (文字列・一行)
  - due_date (日付, 必須)
  - status (ドロップダウン: not_started/in_progress/completed/overdue)
  - priority (ドロップダウン: high/medium/low)
  - completed_at (日時)
  - completed_by (文字列・一行)
  - notes (文字列・複数行)

#### C5. 案件説明資料 (project_documents)
- **アプリコード**: `project_documents`
- **用途**: 案件ごとの説明資料管理
- **主要フィールド**:
  - document_id (文字列・一行, 必須, ユニーク)
  - project_id (文字列・一行, 必須)
  - title (文字列・一行, 必須)
  - document_type (ドロップダウン: manual/notice/map/other)
  - file (添付ファイル)
  - uploaded_by (文字列・一行)
  - uploaded_at (日時)
  - is_public (ドロップダウン: はい/いいえ)
  - notes (文字列・複数行)

---

### 6️⃣ ルールマスタアプリ（2個）

#### R1. タスクテンプレート (task_templates)
- **アプリコード**: `task_templates`
- **用途**: 案件種別ごとのタスクテンプレート
- **主要フィールド**:
  - template_id (文字列・一行, 必須, ユニーク)
  - project_type_id (文字列・一行, 必須)
  - title (文字列・一行, 必須)
  - description (文字列・複数行)
  - relative_due_days (数値) ※案件開始日からの相対日数
  - priority (ドロップダウン: high/medium/low)
  - is_active (ドロップダウン: 有効/無効)

#### R2. インセンティブルール (incentive_rules)
- **アプリコード**: `incentive_rules`
- **用途**: インセンティブ条件と金額の設定
- **主要フィールド**:
  - rule_id (文字列・一行, 必須, ユニーク)
  - name (文字列・一行, 必須)
  - project_id (文字列・一行) ※NULLなら全案件共通
  - condition_type (ドロップダウン: 皆勤/紹介/売上達成/その他)
  - condition_json (文字列・複数行) ※JSON形式
  - incentive_amount (数値, 必須)
  - is_for_invoice (ドロップダウン: はい/いいえ)
  - is_for_payout (ドロップダウン: はい/いいえ)
  - valid_from (日付)
  - valid_until (日付)
  - is_active (ドロップダウン: 有効/無効)

---

## 📦 導入順序

1. **Phase 1: マスタアプリ作成** (M1-M5)
   - CSVインポートでテストデータ投入
   
2. **Phase 2: 単価・ルールマスタ作成** (P1-P3, R1-R2)
   - CSVインポートでテストデータ投入
   
3. **Phase 3: 案件・シフト作成** (T1-T2)
   - CSVインポートでテストデータ投入
   
4. **Phase 4: アサイン・実績取込作成** (T3-T4)
   - CSVインポートでテストデータ投入
   
5. **Phase 5: 請求・支払・経費・インセンティブ作成** (B1-B6)
   - Pythonスクリプトから生成
   
6. **Phase 6: 締め・管理アプリ作成** (C1-C5)
   - Pythonスクリプトから生成

---

## 📊 アプリ一覧サマリ

| カテゴリ | アプリ数 | 用途 |
|---------|---------|------|
| マスタアプリ (M) | 5個 | 稼働者、クライアント、現場、案件種別、役割 |
| 単価マスタ (P) | 3個 | 売上単価、外注単価、単価ルール |
| トランザクション (T) | 4個 | 案件、シフト枠、アサイン、実績取込 |
| 請求・支払 (B) | 6個 | 請求書、支払明細、経費、インセンティブ、送信履歴、銀行振込 |
| 締め・管理 (C) | 5個 | 締め管理、備品マスタ、備品貸出、タスク、案件資料 |
| ルールマスタ (R) | 2個 | タスクテンプレート、インセンティブルール |
| **合計** | **25個** | |

---

## 🔗 連携イメージ

```
[Kintone] ←REST API→ [Python Backend]
  ↓ CSVエクスポート      ↓ 
  ↓                    ↓ CSV取り込み
  ↓                    ↓ 請求書生成
  ↓ REST API           ↓ 支払明細生成
  ↓ ←結果登録─────────  ↓
```

---

## 📄 提供するCSVファイル

1. `workers.csv` - テスト用稼働者 (10名)
2. `clients.csv` - テストクライアント (3社)
3. `sites.csv` - テスト現場 (5現場)
4. `project_types.csv` - 案件種別 (3種)
5. `roles.csv` - 役割 (3種)
6. `price_sales.csv` - 売上単価 (10件)
7. `price_outsource.csv` - 外注単価 (10件)
8. `projects.csv` - テスト案件 (3件)
9. `shift_slots.csv` - 2026年1月のシフト (30件)
10. `assignments.csv` - アサイン (30件)
11. `actuals_sample.csv` - 実績サンプル (CSV取り込みテスト用)

---

## 🚀 次のステップ

1. Kintoneで上記アプリを作成
2. 提供するCSVをインポート
3. Python側でKintone REST APIクライアントを実装
4. データ連携テスト実行
