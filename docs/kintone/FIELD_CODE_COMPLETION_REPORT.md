# Kintone フィールドコード統一 - 完了レポート

**実施日**: 2026年1月28日  
**実施者**: GitHub Copilot + User  

---

## 📊 実施結果サマリ

### 全20アプリの処理状況

| ステータス | アプリ数 | 説明 |
|----------|---------|------|
| ✅ フィールドコード変更完了 | 16 | API経由で日本語→英語に変換 |
| ✅ 既にフィールドコード英語 | 4 | CSVから作成済み、変換不要 |
| **合計** | **20** | **全アプリ処理完了** |

---

## ✅ フィールドコード変更完了（16アプリ）

### マスタ系（5アプリ）

| アプリID | アプリ名 | フィールド数 | 実施日 |
|---------|---------|------------|--------|
| 165 | workers（稼働者マスタ） | 3 | 2026-01-27 |
| 167 | clients（クライアントマスタ） | 4 | 2026-01-27 |
| 166 | sites（現場マスタ） | 4 | 2026-01-27 |
| 163 | roles（役割マスタ） | 3 | 2026-01-27 |
| 164 | project_types（案件種別マスタ） | 3 | 2026-01-27 |
| **小計** | **5アプリ** | **17フィールド** | - |

### トランザクション系（10アプリ）

| アプリID | アプリ名 | フィールド数 | 実施日 |
|---------|---------|------------|--------|
| 160 | projects（案件） | 9 | 2026-01-28 |
| 168 | actuals（実績） | 13 | 2026-01-28 |
| 158 | assignments（アサイン） | 8 | 2026-01-28 |
| 159 | shift_slots（シフト枠） | 7 | 2026-01-28 |
| 162 | price_sales（売上単価マスタ） | 9 | 2026-01-28 |
| 161 | price_outsource（外注単価マスタ） | 9 | 2026-01-28 |
| 157 | price_rules（単価ルール） | 9 | 2026-01-28 |
| 151 | expenses（経費） | 13 | 2026-01-28 |
| 150 | incentives（インセンティブ） | 12 | 2026-01-28 |
| 148 | bank_transfer_batches（振込バッチ） | 12 | 2026-01-28 |
| **小計** | **10アプリ** | **101フィールド** | - |

### マスタ系（追加1アプリ）

| アプリID | アプリ名 | フィールド数 | 実施日 |
|---------|---------|------------|--------|
| 152 | incentive_rules（インセンティブルール） | 11 | 2026-01-28 |
| **小計** | **1アプリ** | **11フィールド** | - |

### 合計

**16アプリ、129フィールド** のフィールドコードを日本語から英語に変換完了 ✅

---

## ✅ 既にフィールドコード英語（4アプリ）

これらのアプリはCSVから作成されたため、最初からフィールドコードが英語でした。

| アプリID | アプリ名 | 状態 | CSVファイル |
|---------|---------|------|------------|
| 147 | equipment（備品マスタ） | ✅ 英語 | equipment_sjis.csv |
| 146 | equipment_loans（貸出備品記録） | ✅ 英語 | equipment_loans_sjis.csv |
| 145 | tasks（タスク進捗） | ✅ 英語 | tasks_sjis.csv |
| 144 | project_documents（案件説明資料） | ✅ 英語 | project_documents_sjis.csv |

**フィールド例**:
- equipment: `equipment_id`, `name`, `category`, `description`, `total_stock`, `available_stock`
- equipment_loans: `loan_id`, `equipment_id`, `worker_id`, `project_id`, `loan_date`, `status`
- tasks: `task_id`, `project_id`, `title`, `description`, `assignee_id`, `due_date`, `status`
- project_documents: `document_id`, `project_id`, `title`, `document_type`, `uploaded_by`

**次のステップ**: APIトークンを.envに追加
```bash
KINTONE_TOKEN_EQUIPMENT=（Kintoneで作成したトークン）
KINTONE_TOKEN_EQUIPMENT_LOANS=（Kintoneで作成したトークン）
KINTONE_TOKEN_TASKS=（Kintoneで作成したトークン）
KINTONE_TOKEN_PROJECT_DOCUMENTS=（Kintoneで作成したトークン）
```

---

## 📈 作業履歴

### フェーズ1: マスタ系5アプリ（2026-01-27）

```bash
python scripts/update_kintone_field_types.py 165  # workers
python scripts/update_kintone_field_types.py 167  # clients
python scripts/update_kintone_field_types.py 166  # sites
python scripts/update_kintone_field_types.py 163  # roles
python scripts/update_kintone_field_types.py 164  # project_types
```

**結果**: 5アプリ、17フィールド変更成功 ✅

### フェーズ2: トランザクション系10アプリ（2026-01-28 00:00）

```bash
python scripts/update_all_field_codes.py
```

**問題発生**: 確認プロンプト（`input()`）で8時間停止 ⏸️

### フェーズ3: スクリプト修正と再実行（2026-01-28 08:00-08:30）

**修正内容**:
```python
# 修正前
confirm = input(f"    {app_name} を変更しますか？ [y/n]: ")

# 修正後
auto_yes = "--yes" in sys.argv or "-y" in sys.argv
if not auto_yes:
    confirm = input(f"    {app_name} を変更しますか？ [y/n]: ")
```

**再実行**:
```bash
python scripts/update_all_field_codes.py --yes
```

**結果**: 10アプリ、101フィールド変更成功 ✅

### フェーズ4: 追加アプリ処理（2026-01-28 10:00）

**アプリID修正**:
- equipment: 169 → **147**（正）
- equipment_loans: 170 → **146**（正）
- tasks: 171 → **145**（正）
- project_documents: 172 → **144**（正）
- incentive_rules: 173 → **152**（正）

**実行**:
```bash
python scripts/update_all_field_codes.py --yes
```

**結果**:
- ✅ incentive_rules (152): 11フィールド変更成功
- ℹ️ equipment (147): 既に英語（変換不要）
- ℹ️ equipment_loans (146): 既に英語（変換不要）
- ℹ️ tasks (145): 既に英語（変換不要）
- ℹ️ project_documents (144): 既に英語（変換不要）

---

## 🔧 使用したツール

### 1. extract_kintone_fields.py
フィールド定義をJSON形式で取得

**使用例**:
```bash
python scripts/extract_kintone_fields.py 165
```

**出力**: `kintone_app/field_mappings/workers_fields.json`

### 2. update_kintone_field_types.py
個別アプリのフィールドコード変更（手動実行用）

**使用例**:
```bash
python scripts/update_kintone_field_types.py 165
```

### 3. update_all_field_codes.py
全アプリのフィールドコードを一括変更（バッチ実行用）

**使用例**:
```bash
# Dry-run（変更内容確認のみ）
python scripts/update_all_field_codes.py --dry-run

# 本番実行（自動承認）
python scripts/update_all_field_codes.py --yes
```

---

## 📝 変更内容の詳細

### 変更パターン

**日本語フィールドコード → 英語フィールドコード**

| 元のコード | 変更後 | 型 |
|-----------|--------|-----|
| ドロップダウン | worker_id | DROP_DOWN |
| ドロップダウン_0 | name | DROP_DOWN |
| ドロップダウン_1 | phone | DROP_DOWN |
| ラジオボタン | client_id | RADIO_BUTTON |
| ラジオボタン_0 | name | RADIO_BUTTON |
| 文字列__1行_ | notes | SINGLE_LINE_TEXT |
| 日付 | start_date | DATE |
| 時刻 | start_time | TIME |
| 数値 | unit_price | NUMBER |

### API処理フロー

1. **フィールド定義取得**: `GET /app/form/fields.json`
2. **プレビュー更新**: `PUT /preview/app/form/fields.json`
3. **アプリデプロイ**: `POST /preview/app/deploy.json`

---

## 🎯 達成した目標

1. ✅ **全20アプリのフィールドコードを英語化**
   - API経由変換: 16アプリ（129フィールド）
   - CSV作成時に英語: 4アプリ

2. ✅ **DB→Kintone同期の準備完了**
   - フィールドコードが統一され、マッピング不要に
   - `format_kintone_record()`で直接同期可能

3. ✅ **自動化スクリプト整備**
   - 確認プロンプト問題を解決（--yesオプション追加）
   - 一括処理スクリプト完成

4. ✅ **ドキュメント整備**
   - FIELD_CODE_CONVERSION.md（全記録）
   - REQUIRED_APPS_FIELDS.md（未処理アプリ定義）
   - FILE_INDEX.md（インデックス更新）

---

## 🚀 次のステップ

### 1. APIトークンを.envに追加（4アプリ）

```bash
# .envファイルに追加
KINTONE_TOKEN_EQUIPMENT=xxxxx
KINTONE_TOKEN_EQUIPMENT_LOANS=xxxxx
KINTONE_TOKEN_TASKS=xxxxx
KINTONE_TOKEN_PROJECT_DOCUMENTS=xxxxx
```

### 2. データ同期テスト

```bash
python scripts/sync_db_to_kintone.py all
```

### 3. 選択肢制約の削除（必要に応じて）

**オプションA**: フィールドタイプをSINGLE_LINE_TEXTに手動変更
- [MANUAL_FIELD_TYPE_CHANGE.md](./MANUAL_FIELD_TYPE_CHANGE.md) 参照

**オプションB**: 選択肢をダミーに変更
```bash
python scripts/clear_kintone_field_options.py 165 167 166 163 164
```

### 4. invoices/payoutsアプリ作成

Kintoneで以下のアプリを新規作成：
- invoices（請求書）
- payouts（支払明細）

フィールド定義: [REQUIRED_APPS_FIELDS.md](./REQUIRED_APPS_FIELDS.md) 参照

---

## 📚 関連ドキュメント

| ドキュメント | 説明 |
|------------|------|
| [FIELD_CODE_CONVERSION.md](./FIELD_CODE_CONVERSION.md) | フィールドコード変更の全記録 |
| [REQUIRED_APPS_FIELDS.md](./REQUIRED_APPS_FIELDS.md) | 必要アプリのフィールド定義 |
| [KINTONE_SETUP_GUIDE.md](./KINTONE_SETUP_GUIDE.md) | 初期セットアップ手順 |
| [MANUAL_FIELD_TYPE_CHANGE.md](./MANUAL_FIELD_TYPE_CHANGE.md) | 手動フィールドタイプ変更ガイド |
| [../FILE_INDEX.md](../FILE_INDEX.md) | ファイルインデックス |

---

**完了日**: 2026年1月28日  
**作成者**: GitHub Copilot  
**ステータス**: ✅ 全20アプリ処理完了
