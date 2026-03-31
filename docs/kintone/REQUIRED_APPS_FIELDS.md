# 必要アプリのフィールド定義

## 1. 備品マスタ (equipment)

**アプリID**: 147  
**仕様参照**: DESIGN_SPEC_v0.3 セクション21.2  
**状態**: ✅ アプリ存在、フィールドコードは英語（CSVで確認済み）  
**運用手順**: `.env` に APIトークンを設定 → `KINTONE_TOKEN_EQUIPMENT=`

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| equipment_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| name | 文字列（1行） | ✅ | 備品名（例: ユニフォーム、無線機、ヘルメット） |
| category | 文字列（1行） | | 分類 |
| description | 文字列（複数行） | | 説明 |
| total_stock | 数値 | | 総在庫数 |
| available_stock | 数値 | | 貸出可能数 |
| notes | 文字列（複数行） | | 備考 |

---

## 2. 貸出備品記録 (equipment_loans)

**アプリID**: 146  
**仕様参照**: DESIGN_SPEC_v0.3 セクション21.3  
**状態**: ✅ アプリ存在、フィールドコードは英語（CSVで確認済み）  
**運用手順**: `.env` に APIトークンを設定 → `KINTONE_TOKEN_EQUIPMENT_LOANS=`

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| loan_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| equipment_id | 文字列（1行） | ✅ | 備品ID（equipmentへの参照） |
| worker_id | 文字列（1行） | ✅ | 貸出先稼働者ID |
| project_id | 文字列（1行） | | 関連案件ID（任意） |
| loan_date | 日付 | ✅ | 貸出日 |
| expected_return_date | 日付 | | 返却予定日 |
| actual_return_date | 日付 | | 実返却日 |
| quantity | 数値 | ✅ | 貸出数 |
| status | ドロップダウン | ✅ | ステータス |
| notes | 文字列（複数行） | | 備考 |

**statusの選択肢**:
- `loaned` - 貸出中
- `returned` - 返却済
- `overdue` - 返却遅延
- `lost` - 紛失

---

## 3. 案件説明資料 (project_documents)
44  
**仕様参照**: DESIGN_SPEC_v0.3 セクション22.2  
**状態**: ✅ アプリ存在、フィールドコードは英語（CSVで確認済み）  
**運用手順**: `.env` に APIトークンを設定 → `KINTONE_TOKEN_PROJECT_DOCUMENTS=`
**仕様参照**: DESIGN_SPEC_v0.3 セクション22.2

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| document_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| project_id | 文字列（1行） | ✅ | 案件ID |
| title | 文字列（1行） | ✅ | 資料タイトル |
| document_type | ドロップダウン | ✅ | 資料種別 |
| file_object_key | 文字列（1行） | | ファイル保存先参照（S3等） |
| uploaded_by | 文字列（1行） | | アップロード者 |
| uploaded_at | 日時 | | アップロード日時 |
| is_public | ラジオボタン | ✅ | 稼働者に公開するか |
| notes | 文字列（複数行） | | 備考 |

**document_typeの選択肢**:
- `manual` - マニュアル
- `notice` - 注意事項
- `map` - 地図・配置図
- `other` - その他

**is_publicの選択肢**:
- `true` - 公開
- `false` - 非公開

---

## 4. タスク進捗 45  
**仕様参照**: DESIGN_SPEC_v0.3 セクション23.2  
**状態**: ✅ アプリ存在、フィールドコードは英語（CSVで確認済み）  
**運用手順**: `.env` に APIトークンを設定 → `KINTONE_TOKEN_TASKS=`
**アプリID**: 171（トークン未設定）  
**仕様参照**: DESIGN_SPEC_v0.3 セクション23.2

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| task_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| project_id | 文字列（1行） | ✅ | 案件ID |
| task_template_id | 文字列（1行） | | テンプレートID（テンプレートから生成した場合） |
| title | 文字列（1行） | ✅ | タスク名 |
| description | 文字列（複数行） | | 詳細説明 |
| assignee_id | 文字列（1行） | | 担当者ID（user_id または worker_id） |
| due_date | 日付 | ✅ | 期限日 |
| status | ドロップダウン | ✅ | ステータス |
| priority | ドロップダウン | ✅ | 優先度 |
| completed_at | 日時 | | 完了日時 |
| completed_by | 文字列（1行） | | 完了者 |
| notes | 文字列（複数行） | | 備考 |

**statusの選択肢**:
- `not_started` - 未着手
- `in_progress` - 進行中
- `completed` - 完了
- `overdue` - 期限超過

**priorityの選択肢**:
- `high` - 高
- `medium` - 中
- `low` - 低

---

## 5. メール設定（system_settings）

**アプリID**: （運用で作成したID）  
**用途**: 送信元メールアドレス/表示名の管理（アプリ側で変更可）  
**運用手順**: `.env` に APIトークンを設定 → `KINTONE_TOKEN_SYSTEM_SETTINGS=`  

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| settings_key | 文字列（1行） | ✅ | 設定キー（固定: `email`） |
| smtp_from_email | 文字列（1行） | ✅ | 送信元メールアドレス |
| smtp_from_name | 文字列（1行） | | 送信元表示名 |

---52  
**仕様参照**: DESIGN_SPEC_v0.3 セクション18.2  
**DBモデル**: `IncentiveRule` (src/models/master.py)  
**状態**: ✅ アプリ存在、フィールドコード英語化完了（11フィールド変更済み）

**アプリID**: 173（403エラー - 権限不足）  
**仕様参照**: DESIGN_SPEC_v0.3 セクション18.2  
**DBモデル**: `IncentiveRule` (src/models/master.py)

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| rule_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| name | 文字列（1行） | ✅ | ルール名 |
| project_id | 文字列（1行） | | 案件ID（NULLなら全案件共通） |
| condition_type | 文字列（1行） | ✅ | 条件種別（例: 皆勤、紹介、売上達成） |
| condition_json | 文字列（複数行） | | 条件詳細（JSON形式） |
| incentive_amount | 数値 | ✅ | 支給額 |
| is_for_invoice | ラジオボタン | ✅ | 請求書に計上するか |
| is_for_payout | ラジオボタン | ✅ | 支払明細に計上するか |
| valid_from | 日付 | | 有効期間開始日 |
| valid_until | 日付 | | 有効期間終了日 |
| is_active | ラジオボタン | ✅ | 有効/無効 |
| notes | 文字列（複数行） | | 備考 |

**is_for_invoice / is_for_payout / is_activeの選択肢**:
- `true` - はい
- `false` - いいえ

---

## 6. 請求書 (invoices) - 未作成

**Kintoneに未作成**  
**仕様参照**: DESIGN_SPEC_v0.3 セクション11, 12

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| invoice_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| invoice_number | 文字列（1行） | ✅ | 請求書番号 |
| client_id | 文字列（1行） | ✅ | クライアントID |
| period_key | 文字列（1行） | ✅ | 期間キー（YYYYMM） |
| issue_date | 日付 | ✅ | 発行日 |
| version | 数値 | ✅ | 版番号（訂正時に増加） |
| status | ドロップダウン | ✅ | ステータス |
| total_amount | 数値 | | 合計金額（集計値） |
| pdf_storage_key | 文字列（1行） | | PDF保存先参照 |
| notes | 文字列（複数行） | | 備考 |

**statusの選択肢**:
- `preparing` - 準備中
- `confirmed` - 確定
- `sent` - 送付済
- `paid` - 入金済
- `superseded` - 訂正済（旧版）

---

## 7. 支払明細 (payouts) - 未作成

**Kintoneに未作成**  
**仕様参照**: DESIGN_SPEC_v0.3 セクション13, 14

### フィールド:

| フィールドコード | 型 | 必須 | 説明 |
|---------------|-----|------|------|
| payout_id | 文字列（1行） | ✅ | 一意識別子（ULID） |
| payout_number | 文字列（1行） | ✅ | 支払明細番号 |
| worker_id | 文字列（1行） | ✅ | 稼働者ID |
| period_key | 文字列（1行） | ✅ | 期間キー（YYYYMM） |
| issue_date | 日付 | ✅ | 発行日 |
| version | 数値 | ✅ | 版番号（訂正時に増加） |
| status | ドロップダウン | ✅ | ステータス |
| total_amount | 数値 | | 合計金額（集計値） |
| pdf_storage_key | 文字列（1行） | | PDF保存先参照 |
| notes | 文字列（複数行） | | 備考 |

**statusの選択肢**:
- `preparing` - 準備中
- `confirmed` - 確定
- `paid` - 支払済
- `superseded` - 訂正済（旧版）

---

## 次のステップ

### 1. APIトークン作成（5アプリ）

Kintoneで以下のアプリのAPIトークンを作成し、.envに追加：

```bash
KINTONE_TOKEN_EQUIPMENT=
KINTONE_TOKEN_EQUIPMENT_LOANS=
KINTONE_TOKEN_TASKS=
KINTONE_TOKEN_PROJECT_DOCUMENTS=
KINTONE_TOKEN_INCENTIVE_RULES=
KINTONE_TOKEN_SYSTEM_SETTINGS=
```

**必要な権限**:
- ✅ レコード閲覧/追加/編集/削除
- ✅ アプリの設定

### 2. フィールドコード変更

トークン設定後、フィールドコードを英語に変更：

```bash
python scripts/update_all_field_codes.py --yes
```

### 3. 新規アプリ作成（2アプリ）

Kintoneで以下のアプリを新規作成：
- invoices（請求書）
- payouts（支払明細）

作成後、上記のフィールド定義に従ってフィールドを設定し、
フィールドコードを最初から英語で設定してください。

### 4. 関連ドキュメント

- [FIELD_CODE_CONVERSION.md](./FIELD_CODE_CONVERSION.md) - フィールドコード変更の全記録
- [KINTONE_SETUP_GUIDE.md](./KINTONE_SETUP_GUIDE.md) - 初期セットアップ手順
- [DESIGN_SPEC_v0.3.md](../spec/DESIGN_SPEC_v0.3.md) - 仕様書（セクション21-23）

---

**作成日**: 2026年1月28日  
**作成者**: GitHub Copilot
