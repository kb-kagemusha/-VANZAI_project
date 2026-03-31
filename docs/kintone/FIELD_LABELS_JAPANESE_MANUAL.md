# Kintoneフィールド名 日本語化マニュアル

## 概要
Kintoneアプリのフィールド名（表示名）を日本語に変更する手順書です。
フィールドコードは英語のまま維持し、ユーザーに表示される名前のみを日本語化します。

## 重要事項
- **フィールドコードは変更しません**（データ連携に影響するため）
- **フィールド名（ラベル）のみ変更します**（表示名のみ）
- ゲストスペース内のアプリはAPI経由での一括変更ができないため、Web UI経由で手動変更が必要です

---

## 変更手順

### ステップ1: アプリの設定画面を開く
1. Kintoneにログイン
2. 対象のアプリを開く
3. 右上の⚙️（歯車アイコン）→「アプリの設定」をクリック
4. 「フォーム」→「フィールドの編集」をクリック

### ステップ2: フィールド名を変更
1. 変更したいフィールドをクリック
2. 「フィールド名」欄を日本語に変更
3. 「フィールドコード」は**変更しない**
4. 「保存」をクリック

### ステップ3: 変更を反映
1. 右上の「設定を完了」をクリック
2. 「アプリを更新する」をクリック

---

## フィールド名マッピング（日本語化リスト）

### 共通フィールド
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `id` | id | **ID** |
| `created_at` | created_at | **作成日時** |
| `updated_at` | updated_at | **更新日時** |
| `is_active` | is_active | **有効** |
| `notes` | notes | **備考** |

---

### 1. 稼働者マスタ（workers - アプリID: 165）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `worker_id` | worker_id | **稼働者ID** |
| `name` | name | **氏名** |
| `phone` | phone | **電話番号** |
| `email` | email | **メールアドレス** |
| `hire_date` | hire_date | **入社日** |
| `termination_date` | termination_date | **退職日** |
| `bank_name` | bank_name | **銀行名** |
| `bank_branch` | bank_branch | **支店名** |
| `bank_account_type` | bank_account_type | **口座種別** |
| `bank_account_number` | bank_account_number | **口座番号** |
| `bank_account_holder` | bank_account_holder | **口座名義** |
| `introducer_name` | introducer_name | **紹介者名** |
| `introducer_supplier_id` | introducer_supplier_id | **紹介者（下請けID）** |
| `is_active` | is_active | **有効** |
| `notes` | notes | **備考** |

---

### 2. クライアントマスタ（clients - アプリID: 167）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `client_id` | client_id | **クライアントID** |
| `name` | name | **クライアント名** |
| `contact_person` | contact_person | **担当者名** |
| `contact_phone` | contact_phone | **連絡先電話** |
| `contact_email` | contact_email | **連絡先メール** |
| `billing_address` | billing_address | **請求先住所** |
| `billing_email` | billing_email | **請求先メール** |
| `payment_terms` | payment_terms | **支払条件** |
| `payment_method` | payment_method | **支払方法** |
| `notes` | notes | **備考** |

---

### 3. 現場マスタ（sites - アプリID: 166）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `site_id` | site_id | **現場ID** |
| `name` | name | **現場名** |
| `site_address` | site_address | **現場住所** |
| `site_contact` | site_contact | **現場連絡先** |
| `client_id` | client_id | **クライアントID** |
| `site_type` | site_type | **現場種別** |
| `notes` | notes | **備考** |

---

### 4. 役割マスタ（roles - アプリID: 163）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `role_id` | role_id | **役割ID** |
| `name` | name | **役割名** |
| `description` | description | **説明** |
| `requires_license` | requires_license | **資格必須** |

---

### 5. 案件種別マスタ（project_types - アプリID: 164）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `project_type_id` | project_type_id | **案件種別ID** |
| `name` | name | **種別名** |
| `description` | description | **説明** |
| `default_unit` | default_unit | **デフォルト単位** |
| `allow_overtime` | allow_overtime | **残業可** |

---

### 6. 売上単価マスタ（price_sales - アプリID: 162）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `price_sales_id` | price_sales_id | **売上単価ID** |
| `client_id` | client_id | **クライアントID** |
| `role_id` | role_id | **役割ID** |
| `project_type_id` | project_type_id | **案件種別ID** |
| `project_id` | project_id | **案件ID** |
| `unit_price` | unit_price | **単価** |
| `unit` | unit | **単位** |
| `effective_from` | effective_from | **有効期間開始** |
| `effective_to` | effective_to | **有効期間終了** |
| `overtime_rate` | overtime_rate | **残業割増率** |
| `late_night_rate` | late_night_rate | **深夜割増率** |
| `notes` | notes | **備考** |

---

### 7. 外注単価マスタ（price_outsource - アプリID: 161）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `price_outsource_id` | price_outsource_id | **外注単価ID** |
| `supplier_id` | supplier_id | **下請けID** |
| `worker_id` | worker_id | **稼働者ID** |
| `role_id` | role_id | **役割ID** |
| `project_id` | project_id | **案件ID** |
| `unit_price` | unit_price | **単価** |
| `unit` | unit | **単位** |
| `effective_from` | effective_from | **有効期間開始** |
| `effective_to` | effective_to | **有効期間終了** |
| `overtime_rate` | overtime_rate | **残業割増率** |
| `late_night_rate` | late_night_rate | **深夜割増率** |
| `notes` | notes | **備考** |

---

### 8. 単価ルールマスタ（price_rules - アプリID: 157）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `rule_id` | rule_id | **ルールID** |
| `name` | name | **ルール名** |
| `rule_type` | rule_type | **ルール種別** |
| `priority` | priority | **優先度** |
| `condition_json` | condition_json | **条件JSON** |
| `action_json` | action_json | **アクションJSON** |
| `is_active` | is_active | **有効** |

---

### 9. 案件マスタ（projects - アプリID: 160）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `project_id` | project_id | **案件ID** |
| `name` | name | **案件名** |
| `start_date` | start_date | **開始日** |
| `end_date` | end_date | **終了日** |
| `project_type_id` | project_type_id | **案件種別ID** |
| `client_id` | client_id | **クライアントID** |
| `site_id` | site_id | **現場ID** |
| `status` | status | **ステータス** |
| `budget` | budget | **予算** |
| `actual_cost` | actual_cost | **実績コスト** |
| `project_manager` | project_manager | **案件責任者** |
| `notes` | notes | **備考** |
| `request_title` | request_title | **タイトル** |
| `request_project_type` | request_project_type | **案件種別（名称）** |
| `request_date` | request_date | **実施日** |
| `request_weekday` | request_weekday | **曜日** |
| `request_facility` | request_facility | **施設名** |
| `request_event_name` | request_event_name | **イベント名** |
| `request_address` | request_address | **住所** |
| `request_content` | request_content | **内容** |
| `director_count` | director_count | **ディレクター人数** |
| `director_days` | director_days | **ディレクター日数** |
| `staff_count` | staff_count | **スタッフ人数** |
| `staff_days` | staff_days | **スタッフ日数** |
| `meeting_time` | meeting_time | **集合時間** |
| `work_start_time` | work_start_time | **稼働開始** |
| `work_end_time` | work_end_time | **稼働終了** |
| `work_hours` | work_hours | **稼働時間(時間)** |
| `dismissal_time` | dismissal_time | **解散時間** |
| `director_unit_price` | director_unit_price | **ギャラ_ディレクター(円/日/人)** |
| `staff_unit_price` | staff_unit_price | **ギャラ_スタッフ(円/日/人)** |
| `director_labor_cost` | director_labor_cost | **人件費合計_ディレクター(円)** |
| `staff_labor_cost` | staff_labor_cost | **人件費合計_スタッフ(円)** |
| `total_labor_cost` | total_labor_cost | **人件費合計(円)** |

---

### 10. シフト枠（shift_slots - アプリID: 159）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `shift_id` | shift_id | **シフトID** |
| `project_id` | project_id | **案件ID** |
| `work_date` | work_date | **シフト日** |
| `start_time` | start_time | **開始時刻** |
| `end_time` | end_time | **終了時刻** |
| `role_id` | role_id | **役割ID** |
| `required_count` | required_count | **必要人数** |
| `confirmed_count` | confirmed_count | **確定人数** |
| `notes` | notes | **備考** |

---

### 11. アサイン（assignments - アプリID: 158）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `assignment_id` | assignment_id | **アサインID** |
| `shift_id` | shift_id | **シフトID** |
| `worker_id` | worker_id | **稼働者ID** |
| `role_id` | role_id | **役割ID** |
| `assignment_date` | assignment_date | **アサイン日** |
| `status` | status | **アサインステータス** |
| `cancel_reason` | cancel_reason | **キャンセル理由** |
| `confirmed_at` | confirmed_at | **確定日時** |
| `notes` | notes | **備考** |

---

### 12. 実績（actuals - アプリID: 168）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `actual_id` | actual_id | **実績ID** |
| `assignment_id` | assignment_id | **アサインID** |
| `worker_id` | worker_id | **稼働者ID** |
| `project_id` | project_id | **案件ID** |
| `role_id` | role_id | **役割ID** |
| `work_date` | work_date | **稼働日** |
| `start_time` | start_time | **開始時刻** |
| `end_time` | end_time | **終了時刻** |
| `break_minutes` | break_minutes | **休憩時間（分）** |
| `actual_hours` | actual_hours | **実績時間** |
| `overtime_hours` | overtime_hours | **残業時間** |
| `late_night_hours` | late_night_hours | **深夜時間** |
| `import_batch_id` | import_batch_id | **取込バッチID** |
| `error_reason` | error_reason | **エラー理由** |

---

### 13. 経費（expenses - アプリID: 151）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `expense_id` | expense_id | **経費ID** |
| `worker_id` | worker_id | **稼働者ID** |
| `project_id` | project_id | **案件ID** |
| `expense_date` | expense_date | **経費日** |
| `category` | category | **カテゴリ** |
| `amount` | amount | **金額** |
| `description` | description | **説明** |
| `receipt_number` | receipt_number | **領収書番号** |
| `status` | status | **承認ステータス** |
| `approved_by` | approved_by | **承認者** |
| `approved_at` | approved_at | **承認日時** |
| `invoice_id` | invoice_id | **請求書ID** |

---

### 14. インセンティブ（incentives - アプリID: 152）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `incentive_id` | incentive_id | **インセンティブID** |
| `worker_id` | worker_id | **稼働者ID** |
| `project_id` | project_id | **案件ID** |
| `period_start` | period_start | **期間開始** |
| `period_end` | period_end | **期間終了** |
| `incentive_type` | incentive_type | **インセンティブ種別** |
| `amount` | amount | **金額** |
| `calculation_base` | calculation_base | **計算根拠** |
| `approved_by` | approved_by | **承認者** |
| `approved_at` | approved_at | **承認日時** |
| `payout_id` | payout_id | **支払ID** |

---

### 15. 下請け（紹介者）マスタ（suppliers - アプリID: 187）
| フィールドコード | 現在の名前 | 日本語名 |
|:----------------|:----------|:--------|
| `supplier_id` | supplier_id | **紹介者ID** |
| `name` | name | **紹介者名** |
| `contact_email` | contact_email | **連絡先メール** |
| `contact_phone` | contact_phone | **連絡先電話** |
| `payout_terms_days` | payout_terms_days | **支払サイト（日数）** |
| `default_daily_price` | default_daily_price | **日額単価** |
| `is_active` | is_active | **有効フラグ** |
| `notes` | notes | **備考** |
| `created_at` | created_at | **作成日時** |
| `updated_at` | updated_at | **更新日時** |

---

## 一括変更用CSVエクスポート/インポート（代替手段）

### 方法1: CSV編集による一括変更
1. Kintoneアプリからデータをエクスポート
2. ヘッダー行（フィールド名）を日本語に変更
3. Kintoneにインポート（ヘッダーマッピング画面で対応付け）

**注意**: この方法ではフィールド名は変わりません。データの列名のみ変わります。

### 方法2: APIトークンに「アプリ設定権限」を付与
1. Kintoneアプリの設定 → APIトークン
2. 既存トークンの権限に「**アプリ設定権限**」を追加
3. 再度スクリプトを実行: `python scripts/update_kintone_field_labels_to_japanese.py all`

**注意**: セキュリティリスクが高いため、作業完了後はすぐに権限を削除してください。

---

## 対象アプリ一覧

- 1. 稼働者マスタ（workers）
- 2. クライアントマスタ（clients）
- 3. 現場マスタ（sites）
- 4. 役割マスタ（roles）
- 5. 案件種別マスタ（project_types）
- 6. 売上単価マスタ（price_sales）
- 7. 外注単価マスタ（price_outsource）
- 8. 単価ルールマスタ（price_rules）
- 9. 案件マスタ（projects）
- 10. シフト枠（shift_slots）
- 11. アサイン（assignments）
- 12. 実績（actuals）
- 13. 経費（expenses）
- 14. インセンティブ（incentives）
- 15. 下請け（紹介者）マスタ（suppliers）

---

## トラブルシューティング

### Q: フィールドコードを変更してしまった場合
A: Kintoneアプリの「設定」→「フォーム」→「フィールドの編集」から、元のフィールドコードに戻してください。データ連携が壊れます。

### Q: 変更が反映されない
A: 「設定を完了」→「アプリを更新する」をクリックしているか確認してください。

### Q: 一部のフィールドが見つからない
A: システムフィールド（レコード番号、作成者、更新者など）は変更できません。

---

## 作成日
2026-01-30

## 更新履歴
- 2026-01-30: 初版作成
