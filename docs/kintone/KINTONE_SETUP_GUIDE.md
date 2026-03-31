# Kintone セットアップガイド

## 📦 準備

### 必要なもの
- Kintoneアカウント（開発者ライセンスでOK）
- CSVファイル一式（`docs/kintone/csv/` フォルダ内）

---

## 🔧 Phase 1: マスタアプリ作成（5個）

### M1. 稼働者マスタ (workers)

1. **アプリ作成**
   - 「はじめから作成」→「アプリ名: 稼働者マスタ」
   
2. **フィールド設定**
   ```
   worker_id     : 文字列（1行）※必須、重複禁止
   name          : 文字列（1行）※必須
   email         : 文字列（1行）
   phone         : 文字列（1行）
   is_active     : ドロップダウン（有効/無効）
   notes         : 文字列（複数行）
   ```

3. **CSVインポート**
   - 設定 → 「その他の設定」→ 「ファイルから読み込む」
   - `workers.csv` を選択
   - フィールドをマッピング
   - インポート実行

4. **確認**
   - 10件のレコードが登録されていること

---

### M2. クライアントマスタ (clients)

1. **フィールド設定**
   ```
   client_id     : 文字列（1行）※必須、重複禁止
   name          : 文字列（1行）※必須
   code          : 文字列（1行）
   address       : 文字列（複数行）
   billing_email : 文字列（1行）
   notes         : 文字列（複数行）
   ```

2. **CSVインポート**: `clients.csv`（3件）

---

### M3. 現場マスタ (sites)

1. **フィールド設定**
   ```
   site_id       : 文字列（1行）※必須、重複禁止
   name          : 文字列（1行）※必須
   code          : 文字列（1行）
   address       : 文字列（複数行）
   notes         : 文字列（複数行）
   ```

2. **CSVインポート**: `sites.csv`（5件）

---

### M4. 案件種別マスタ (project_types)

1. **フィールド設定**
   ```
   type_id       : 文字列（1行）※必須、重複禁止
   name          : 文字列（1行）※必須
   description   : 文字列（複数行）
   ```

2. **CSVインポート**: `project_types.csv`（3件）

---

### M5. 役割マスタ (roles)

1. **フィールド設定**
   ```
   role_id       : 文字列（1行）※必須、重複禁止
   name          : 文字列（1行）※必須
   description   : 文字列（複数行）
   ```

2. **CSVインポート**: `roles.csv`（3件）

---

## 💰 Phase 2: 単価マスタアプリ（3個）

### P1. 売上単価マスタ (price_sales)

1. **フィールド設定**
   ```
   price_id      : 文字列（1行）※必須、重複禁止
   client_id     : 文字列（1行）
   project_id    : 文字列（1行）
   role_id       : 文字列（1行）
   unit_price    : 数値 ※必須
   valid_from    : 日付
   valid_until   : 日付
   is_default    : ドロップダウン（はい/いいえ）
   notes         : 文字列（複数行）
   ```

2. **CSVインポート**: `price_sales.csv`（9件）

---

### P2. 外注単価マスタ (price_outsource)

1. **フィールド設定**（price_salesと同じ）
   ```
   price_id      : 文字列（1行）※必須、重複禁止
   worker_id     : 文字列（1行）
   project_id    : 文字列（1行）
   role_id       : 文字列（1行）
   unit_price    : 数値 ※必須
   valid_from    : 日付
   valid_until   : 日付
   is_default    : ドロップダウン（はい/いいえ）
   notes         : 文字列（複数行）
   ```

2. **CSVインポート**: `price_outsource.csv`（9件）

---

### P3. 単価ルールマスタ (price_rules)

1. **フィールド設定**
   ```
   rule_id         : 文字列（1行）※必須、重複禁止
   name            : 文字列（1行）※必須
   priority        : 数値
   conditions_json : 文字列（複数行）
   sales_price     : 数値
   outsource_price : 数値
   valid_from      : 日付
   valid_until     : 日付
   is_active       : ドロップダウン（有効/無効）
   ```

2. **手動登録**（ルールは必要に応じて後で追加）

---

## 📋 Phase 3: 案件・シフトアプリ（2個）

### T1. 案件マスタ (projects)

1. **フィールド設定**
   ```
   project_id      : 文字列（1行）※必須、重複禁止
   name            : 文字列（1行）※必須
   client_id       : 文字列（1行）※必須
   site_id         : 文字列（1行）※必須
   project_type_id : 文字列（1行）※必須
   start_date      : 日付 ※必須
   end_date        : 日付
   status          : ドロップダウン（operating/completed/canceled）
   notes           : 文字列（複数行）
   
   # 案件依頼サンプル対応（追加）
   request_title         : 文字列（1行）
   request_project_type  : 文字列（1行）
   request_date          : 日付
   request_weekday       : 文字列（1行）
   request_facility      : 文字列（1行）
   request_event_name    : 文字列（1行）
   request_address       : 文字列（複数行）
   request_content       : 文字列（複数行）
   director_count        : 数値
   director_days         : 数値
   staff_count           : 数値
   staff_days            : 数値
   meeting_time          : 時刻
   work_start_time       : 時刻
   work_end_time         : 時刻
   work_hours            : 数値
   dismissal_time        : 時刻
   director_unit_price   : 数値
   staff_unit_price      : 数値
   director_labor_cost   : 数値
   staff_labor_cost      : 数値
   total_labor_cost      : 数値
   ```

2. **CSVインポート**: `projects.csv`（3件）
   - 案件依頼サンプルの取り込みテンプレ: [kintone_app/sample/案件サンプル_取込テンプレ.csv](../../kintone_app/sample/%E6%A1%88%E4%BB%B6%E3%82%B5%E3%83%B3%E3%83%97%E3%83%AB_%E5%8F%96%E8%BE%BC%E3%83%86%E3%83%B3%E3%83%97%E3%83%AC.csv)

---

### T2. シフト枠 (shift_slots)

1. **フィールド設定**
   ```
   slot_id        : 文字列（1行）※必須、重複禁止
   project_id     : 文字列（1行）※必須
   work_date      : 日付 ※必須
   start_time     : 時刻 ※必須
   end_time       : 時刻 ※必須
   required_count : 数値
   notes          : 文字列（複数行）
   ```

2. **CSVインポート**: `shift_slots.csv`（15件）

---

## 👥 Phase 4: アサインメント（1個）

### T3. アサインメント (assignments)

1. **フィールド設定**
   ```
   assignment_id          : 文字列（1行）※必須、重複禁止
   shift_slot_id          : 文字列（1行）※必須
   worker_id              : 文字列（1行）※必須
   role_id                : 文字列（1行）※必須
   status                 : ドロップダウン（tentative/confirmed/canceled）
   locked_price_sales     : 数値
   locked_price_outsource : 数値
   notes                  : 文字列（複数行）
   ```

2. **CSVインポート**: `assignments.csv`（18件）

---

## 📤 Phase 5: 実績CSV取り込みテスト

### T4. 実績CSV取り込みアプリ (actuals_import)

1. **アプリ作成**
   ```
   batch_id      : 文字列（1行）※必須、重複禁止
   file_name     : 文字列（1行）※必須
   project_id    : 文字列（1行）
   period_key    : 文字列（1行）
   mode          : ドロップダウン（replace_scope/append）
   status        : ドロップダウン（completed/failed/partial_error）
   count_success : 数値
   count_error   : 数値
   submitted_by  : 文字列（1行）
   submit_date   : 日時
   errors_json   : 文字列（複数行）
   ```

2. **実績CSVサンプル**
   - `actuals_sample.csv` を準備
   - Python側のCSV importスクリプトで処理

---

## 🧪 動作確認

### 1. データ確認
```
✓ 稼働者: 10名
✓ クライアント: 3社
✓ 現場: 5箇所
✓ 案件種別: 3種
✓ 役割: 3種
✓ 売上単価: 9件
✓ 外注単価: 9件
✓ 案件: 3件
✓ シフト枠: 15件
✓ アサイン: 18件
```

### 2. リレーション確認
- 案件 → クライアント、現場、案件種別
- シフト枠 → 案件
- アサイン → シフト枠、稼働者、役割

### 3. CSV取込テスト
- `actuals_sample.csv` を使用
- Pythonスクリプトで実行
- 17行の実績が正しく取り込まれること

---

## 🔗 次のステップ

1. ✅ Kintoneアプリセットアップ完了
2. → Python側でKintone REST APIクライアント実装
3. → データ連携テスト
4. → 請求書・支払明細生成テスト
5. → 締め処理テスト

---

## 📞 トラブルシューティング

### Q: CSVインポートで文字化け
A: CSVファイルのエンコーディングを「UTF-8 BOM付き」に変換

### Q: 日付フィールドのインポートエラー
A: 日付形式を「YYYY-MM-DD」に統一

### Q: IDフィールドの重複エラー
A: 既存データを削除してから再インポート

---

## 📝 メモ

- Kintone API Token は各アプリで生成が必要
- REST API のレート制限に注意（1分あたり1000リクエスト）
- 本番運用時はゲストスペースの利用を推奨
