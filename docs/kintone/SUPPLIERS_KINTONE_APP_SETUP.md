# 紹介者（Suppliers）マスタ Kintoneアプリ作成手順

## 概要
下請け（紹介者）マスタをKintoneで管理するためのアプリ作成手順

## 前提条件
- ✅ Kintoneゲストスペース作成済み（KINTONE_GUEST_SPACE_ID=3）
- ✅ アプリ作成権限保有
- ✅ ローカルDBにsuppliersテーブル作成済み

---

## ステップ1: Kintoneアプリ作成

### 1.1 Kintoneにログイン
https://your-subdomain.cybozu.com/k/guest/3/

### 1.2 新規アプリ作成
1. 「アプリを追加する」→「はじめから作成」
2. アプリ名: `suppliers_sjis`
3. アイコン: 任意（🏢など）

### 1.3 フィールド設定

**注記**: フィールド名（表示名）は日本語、フィールドコードは英語のまま運用します。
詳細は [FIELD_LABELS_JAPANESE_MANUAL.md](FIELD_LABELS_JAPANESE_MANUAL.md) の suppliers セクションを参照。

| フィールド名 | フィールドコード | タイプ | 必須 | 備考 |
|:-----------|:---------------|:------|:----|:-----|
| 紹介者ID | `supplier_id` | 文字列(1行) | ✅ | 一意識別子（ULID）。DB（suppliers.id）と同一値を保持する |
| 紹介者名 | `name` | 文字列(1行) | ✅ | 会社名/個人名 |
| 連絡先メール | `contact_email` | 文字列(1行) | ⬜ | |
| 連絡先電話 | `contact_phone` | 文字列(1行) | ⬜ | |
| 支払サイト（日数） | `payout_terms_days` | 数値 | ✅ | デフォルト: 70 |
| 日額単価 | `default_daily_price` | 数値 | ⬜ | DB側はNULL可（未設定時の扱いは運用/生成ロジックに従う） |
| 有効フラグ | `is_active` | ドロップダウン | ✅ | 選択肢: 有効/無効 |
| 備考 | `notes` | 文字列(複数行) | ⬜ | |
| 作成日時 | `created_at` | 作成日時 | - | 自動 |
| 更新日時 | `updated_at` | 更新日時 | - | 自動 |

**選択肢設定（is_active）:**
```
有効
無効
```

### 1.4 アプリを公開
「アプリを公開」→「公開」

### 1.5 CSVから作成した場合の補正（重要）
CSV作成だとフィールドコードが自動生成されるため、**必ずコードを揃える必要があります**。

**自動補正（推奨）**
```powershell
C:/VANZAI_project/.venv/Scripts/python.exe scripts/add_kintone_missing_fields.py
```

**フォーム調整**
- 自動生成コード（ラジオボタン/数値/リンク等）のフィールドは削除
- 正規フィールド（supplier_id, name, contact_email, ...）のみ残す

---

## ステップ2: APIトークン生成

### 2.1 設定画面に移動
「アプリの設定」→「APIトークン」

### 2.2 トークン生成
1. 「生成する」をクリック
2. アクセス権：
   - ✅ レコード閲覧
   - ✅ レコード追加
   - ✅ レコード編集
   - ✅ レコード削除
3. 「保存」→「アプリを更新」

### 2.3 トークンをコピー
生成されたトークンをメモ帳に保存

**例:**
```
AbCdEf123456789GhIjKlMnOpQrStUvWxYz
```

---

## ステップ3: 環境変数設定

### 3.1 `.env` ファイル更新
```powershell
cd C:\VANZAI_project
code .env
```

### 3.2 アプリIDとトークン追加
```env
# 紹介者マスタ（新規追加）
KINTONE_APP_SUPPLIERS=199  # ← 実際のアプリIDに変更
KINTONE_TOKEN_SUPPLIERS=<SET_IN_ENV>  # ← 実際のトークンに変更
```

※ APIトークンは機密情報のため、リポジトリには保存しない（漏えいが疑われる場合はトークン再生成/ローテーション）

---

## ステップ4: データ同期テスト

### 4.1 ローカルDBにサンプルデータ作成
```powershell
C:/VANZAI_project/.venv/Scripts/python.exe -m src.cli.main create-sample-data --suppliers
```

### 4.2 Kintoneへ同期
```powershell
# 初回のみ add で追加
C:/VANZAI_project/.venv/Scripts/python.exe scripts/sync_db_to_kintone.py suppliers --mode add

# 2回目以降は upsert
C:/VANZAI_project/.venv/Scripts/python.exe scripts/sync_db_to_kintone.py suppliers --mode upsert
```

**期待される出力:**
```
============================================================
DB→Kintone データ同期
============================================================

同期対象: suppliers

[紹介者マスタ同期]
アプリID: 199
DB件数: 3
✅ 同期成功: 3 件追加

============================================================
✅ 同期処理完了
============================================================

[サマリ]
  suppliers: ✅ 成功
```

### 4.3 Kintoneで確認
1. https://your-subdomain.cybozu.com/k/guest/3/169/ にアクセス
2. 3件のレコードが追加されていることを確認

---

## ステップ5: Workers アプリに `introducer_supplier_id` フィールド追加

### 5.1 Workers アプリ（ID: 165）を開く
https://your-subdomain.cybozu.com/k/guest/3/165/

### 5.2 フィールド追加
「アプリの設定」→「フォーム」→「フィールド追加」

| フィールド名 | フィールドコード | タイプ | 必須 | 備考 |
|:-----------|:---------------|:------|:----|:-----|
| 紹介者ID（Supplier） | `introducer_supplier_id` | 文字列(1行) | ⬜ | suppliers.supplier_id（ULID）を参照 |

補足: 自動化する場合は `scripts/add_kintone_missing_fields.py` で追加できます。

注意: `introducer_supplier_id` はDBの外部キー（suppliers.id=ULID）なので、数値フィールドにはしないでください。

### 5.3 アプリを更新
「保存」→「アプリを更新」

### 5.4 既存データ更新（必要に応じて）
- workers.introducer_worker_id を持つレコードを特定
- データ移行スクリプトで suppliers レコード作成後、introducer_supplier_id を更新

---

## ステップ6: 運用フロー確立

### 6.1 紹介者登録フロー
1. 新規紹介者（下請け会社/個人）が発生
2. Kintone「suppliers_sjis」アプリに手入力登録
   - 紹介者名、連絡先、支払サイト、日額単価
3. スクリプトでローカルDBに同期（import_master_data.py）
4. Workers登録時に introducer_supplier_id を設定

### 6.2 支払明細生成フロー
1. 月末締め処理
2. PayoutService.generate_supplier_payout() 実行
   - 紹介者配下の稼働者実績を集計
   - 人工単位（worker_id × work_date × project_id のユニーク数）
   - 日額単価 × 人工で支払金額計算
3. 支払明細をKintoneに同期（sync_db_to_kintone.py payouts）

### 6.3 日額単価の管理
- 基本: 16,000円/日（default_daily_price）
- 多田さん派閥: 16,500円/日
- 個別交渉: Supplier.default_daily_price で管理

---

## トラブルシューティング

### Q1: アプリIDが分からない
**A1:** 
1. Kintoneアプリを開く
2. URLを確認: https://xxx.cybozu.com/k/guest/3/**169**/
3. 太字の数字がアプリID

### Q2: APIトークンが無効
**A2:**
1. 「アプリの設定」→「APIトークン」
2. 既存トークンを「再生成」
3. `.env` ファイルの `KINTONE_TOKEN_SUPPLIERS` を更新

### Q3: 同期時にエラー「フィールドコードが存在しない」
**A3:**
1. Kintoneアプリ設定→「フォーム」→「フィールド」を確認
2. フィールドコードが `supplier_id`, `name`, `contact_email` 等と一致しているか確認
3. 不一致の場合は手動修正

### Q4: 既存 workers.introducer_worker_id データの移行方法
**A4:**
```powershell
# データ移行スクリプト実行
C:/VANZAI_project/.venv/Scripts/python.exe scripts/migrate_introducers_to_suppliers.py --dry-run

# 問題なければ実移行
C:/VANZAI_project/.venv/Scripts/python.exe scripts/migrate_introducers_to_suppliers.py
```

---

## 確認事項（運用手順）

- [x] Kintone アプリ「suppliers_sjis」作成完了（アプリID: 187）
- [x] フィールド設定完了（supplier_id, name, contact_email等）
- [x] APIトークン生成完了
- [x] `.env` ファイル更新完了（KINTONE_APP_SUPPLIERS=187, KINTONE_TOKEN_SUPPLIERS）
- [x] データ同期テスト成功（3件同期完了）
- Workers アプリに introducer_supplier_id フィールド追加完了
- 既存データ移行完了（必要に応じて）
- 運用フロー確立（紹介者登録、支払明細生成）

---

## 関連ドキュメント
- [DRV_PAYOUT_RULES.md](../ops/DRV_PAYOUT_RULES.md): drv案件の支払ルール詳細
- [DECISION_LOG.md](../decisions/DECISION_LOG.md): DEC-009（下請けマスタ追加）
- [IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md): Task 22実装詳細
- [sync_db_to_kintone.py](../../scripts/sync_db_to_kintone.py): DB→Kintone同期スクリプト
- [migrate_introducers_to_suppliers.py](../../scripts/migrate_introducers_to_suppliers.py): データ移行スクリプト
