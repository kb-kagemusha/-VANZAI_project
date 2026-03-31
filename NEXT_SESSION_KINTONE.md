# 新セッション用指示文: Kintone実装フェーズ

> 履歴注記（2026-02-16）
> 本書は 2026-01-28 時点の実行計画。現行状態では Kintone実装フェーズは完了扱いで、最新の変更履歴は `docs/IMPLEMENTATION_LOG.md` を参照。

**作成日**: 2026年1月28日  
**前提**: フィールドコード統一作業完了（全20アプリ、166フィールド変換済み）

---

## 🎯 このセッションの目的

Kintoneを実際の業務運用で使えるようにする：
1. CSV取り込みでマスタデータ投入（20アプリ）
2. DB ↔ Kintone 双方向同期の動作確認
3. 運用フローの実証（CSV更新 → DB反映 → 集計 → Kintone出力）

---

## ✅ 前セッション完了事項（2026-01-28 13:00時点）

### フィールドコード統一作業完了

| 項目 | 詳細 |
|-----|------|
| 対象アプリ数 | 20アプリ（全アプリ完了） |
| 変換フィールド数 | 166フィールド |
| .env トークン設定 | 20アプリ分すべて設定済み |
| ドキュメント | `docs/kintone/FIELD_CODE_FINAL_REPORT.md` 参照 |

**重要**: すべてのフィールドコードが英語化されており、Pythonスクリプトとの連携準備が整っています。

### 環境設定済み

- Kintone環境:
  - Subdomain: `xtf5wpxp3gk2`
  - Guest Space ID: `3`
  - Base URL: `https://xtf5wpxp3gk2.cybozu.com/k/guest/3/v1/`
- APIトークン: `.env` に20アプリ分設定済み
- スクリプト:
  - `scripts/update_all_field_codes.py`: フィールドコード一括変換（完了）
  - `scripts/extract_kintone_fields.py`: フィールド定義取得
  - `scripts/import_master_data.py`: CSV→DB取り込み
  - `scripts/sync_db_to_kintone.py`: DB→Kintone同期（未テスト）

---

## 🚀 今回実施するタスク（優先順位順）

### タスク1: CSV取り込みテスト（マスタ5アプリ）

**目的**: フィールドコード変更後のCSV取り込みが正常動作するか確認

**手順**:
1. DBマイグレーション実行（まだの場合）
   ```powershell
   alembic upgrade head
   ```

2. マスタデータCSV取り込み（5アプリ）
   ```powershell
   python scripts/import_master_data.py workers
   python scripts/import_master_data.py clients
   python scripts/import_master_data.py sites
   python scripts/import_master_data.py roles
   python scripts/import_master_data.py project_types
   ```

3. DB確認（SQLiteで件数確認）
   ```powershell
   sqlite3 vanzai.db "SELECT COUNT(*) FROM workers;"
   sqlite3 vanzai.db "SELECT COUNT(*) FROM clients;"
   ```

**期待結果**:
- workers: 10件
- clients: 3件
- sites: 5件
- roles: 3件
- project_types: 3件

**トラブルシューティング**:
- CSVエンコーディングエラー → `kintone_app/*_sjis.csv` を使用
- フィールドコードエラー → `docs/kintone/FIELD_CODE_FINAL_REPORT.md` で変換結果確認

---

### タスク2: DB → Kintone 同期テスト

**目的**: DBデータをKintoneに同期できるか確認

**前提**: タスク1完了（DBにデータが入っている）

**手順**:
1. 同期スクリプト確認
   ```powershell
   cat scripts/sync_db_to_kintone.py
   ```
   - スクリプトが存在しない場合は作成が必要

2. workers アプリで同期テスト
   ```powershell
   python scripts/sync_db_to_kintone.py workers
   ```

3. Kintone UIで確認
   - https://xtf5wpxp3gk2.cybozu.com/k/guest/3/ にアクセス
   - 稼働者マスタ（workers, app_id=165）を開く
   - 10件のレコードが同期されているか確認

**期待結果**:
- Kintoneに10件のworkerレコードが表示される
- フィールド値（worker_id, name, email等）が正しく表示される

**注意点**:
- 重複レコード問題: Kintoneの既存データをクリアしてから同期推奨
- APIレート制限: 60秒/1000リクエスト（通常の運用では問題なし）

---

### タスク3: トランザクションデータ取り込み（10アプリ）

**目的**: 案件・シフト・実績データをDBに投入

**手順**:
1. 案件データ取り込み
   ```powershell
   python scripts/import_master_data.py projects
   ```

2. 実績データ取り込み
   ```powershell
   python scripts/import_master_data.py actuals
   ```

3. その他トランザクションデータ
   ```powershell
   python scripts/import_master_data.py assignments
   python scripts/import_master_data.py shift_slots
   python scripts/import_master_data.py expenses
   python scripts/import_master_data.py incentives
   ```

**確認**:
```powershell
sqlite3 vanzai.db "SELECT COUNT(*) FROM projects;"
sqlite3 vanzai.db "SELECT COUNT(*) FROM actuals;"
```

**注意**:
- CSVサンプルデータは `kintone_app/` フォルダ内
- データ不整合（外部キーエラー等）が発生した場合はCSV修正

---

### タスク4: 集計・請求書生成テスト

**目的**: DBデータから請求書を生成し、Kintoneに出力

**手順**:
1. API起動
   ```powershell
   uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Swagger UIで動作確認
   - http://localhost:8000/docs にアクセス
   - `/api/aggregation/sales` で売上集計テスト
   - `/api/invoice/generate` で請求書生成テスト

3. 生成された請求書をKintoneに同期
   ```powershell
   python scripts/sync_invoices_to_kintone.py
   ```

**期待結果**:
- 請求書PDFが生成される（storage/invoices/ フォルダ）
- Kintone invoicesアプリ（未作成の場合は作成必要）にレコード追加

---

### タスク5: 運用フロー実証

**目的**: 月次運用フローをエンドツーエンドで実行

**シナリオ**: 
1月分の実績締め → 請求書発行 → 支払明細作成 → 振込ファイル生成

**手順**:
1. 実績締め（Hard Close）
   ```powershell
   curl -X POST http://localhost:8000/api/closing/close \
     -H "Content-Type: application/json" \
     -d '{"year": 2026, "month": 1, "close_type": "hard"}'
   ```

2. 請求書一括生成
   ```powershell
   curl -X POST http://localhost:8000/api/invoice/batch_generate \
     -H "Content-Type: application/json" \
     -d '{"year": 2026, "month": 1}'
   ```

3. 支払明細一括生成
   ```powershell
   curl -X POST http://localhost:8000/api/payout/batch_generate \
     -H "Content-Type: application/json" \
     -d '{"year": 2026, "month": 1}'
   ```

4. 振込ファイル生成
   ```powershell
   curl -X POST http://localhost:8000/api/bank_transfer/generate \
     -H "Content-Type: application/json" \
     -d '{"payout_delivery_id": 1}'
   ```

5. 生成物確認
   ```powershell
   ls storage/invoices/
   ls storage/payouts/
   ls storage/bank_transfers/
   ```

**期待結果**:
- 請求書PDF: 3件（クライアント数分）
- 支払明細PDF: 10件（稼働者数分）
- 振込ファイル: 1件（全銀フォーマット）

---

## 📋 トラブルシューティング

### 問題1: CSV取り込みエラー

**症状**: 
```
ValueError: Field 'ドロップダウン' not found in CSV
```

**原因**: フィールドコードが日本語のまま

**解決策**:
1. `scripts/extract_kintone_fields.py [app_id]` でフィールドコード確認
2. 日本語フィールドが残っている場合:
   ```powershell
   python scripts/update_all_field_codes.py [app_name] --yes
   ```

### 問題2: Kintone API認証エラー

**症状**:
```
401 Unauthorized
```

**原因**: APIトークンが無効または未設定

**解決策**:
1. `.env` ファイルでトークン確認
2. Kintone UIでトークン再生成
3. アプリTOKEN一覧.csv と `.env` を照合

### 問題3: DB同期で重複レコード

**症状**:
```
IntegrityError: UNIQUE constraint failed
```

**原因**: Kintone→DB同期で既存レコードと衝突

**解決策**:
1. DBをリセット
   ```powershell
   rm vanzai.db
   alembic upgrade head
   ```
2. CSVから再取り込み

### 問題4: 外部キーエラー

**症状**:
```
ForeignKeyConstraint failed: actuals.worker_id
```

**原因**: マスタデータが未投入

**解決策**:
1. 投入順序を守る: マスタ5アプリ → トランザクション10アプリ
2. workers, clients, sites を先に投入

---

## 📚 参考ドキュメント

### 最優先で読むべきドキュメント

1. **`docs/kintone/FIELD_CODE_FINAL_REPORT.md`**
   - 全20アプリのフィールドコード変換完了レポート
   - トラブルシューティング情報

2. **`docs/kintone/KINTONE_SETUP_GUIDE.md`**
   - Kintoneアプリ作成手順（CSVインポート含む）

3. **`docs/ops/CSV_IMPORT_GUIDE.md`**
   - CSV取り込みの詳細仕様（洗い替えモード、二重化防止）

4. **`RUNBOOK_MONTHLY.md`**
   - 月次運用フロー（実績締め→請求→支払）

5. **`docs/spec/DESIGN_SPEC_v0.3.md`**
   - システム仕様の正本

### スクリプトリファレンス

| スクリプト | 用途 | 引数 |
|-----------|------|------|
| `scripts/import_master_data.py` | CSV→DB取り込み | app_name (workers, clients等) |
| `scripts/sync_db_to_kintone.py` | DB→Kintone同期 | app_name |
| `scripts/extract_kintone_fields.py` | フィールド定義取得 | app_id [app_id...] |
| `scripts/update_all_field_codes.py` | フィールドコード変換 | app_name [app_name...] [--yes] |

---

## 🎯 成功基準

このセッション終了時に以下が達成されていること：

- [x] タスク1完了: マスタ5アプリのCSV取り込み成功（24件のデータがDBに存在）
- [x] タスク2完了: DB→Kintone同期成功（少なくとも1アプリで動作確認）
- [x] タスク3完了: トランザクションデータ取り込み（projects, actuals等がDBに存在）
- [x] タスク4完了: 請求書生成成功（PDF出力確認）
- [x] タスク5完了: 月次運用フロー実証（締め→請求→支払→振込ファイル）

---

## 🔄 次の次のセッションへの引き継ぎ

このセッションで上記タスクが完了したら、次のセッションでは：

1. **本番データ移行**: 実際の業務データをKintoneに投入
2. **権限設定**: ユーザー管理、ロールベースアクセス制御
3. **監視・ログ**: 監査ログの確認、エラー通知設定
4. **パフォーマンステスト**: 大量データでの動作確認
5. **ユーザートレーニング**: 運用マニュアル整備、研修実施

---

## 🚨 絶対に守るルール（AGENTS.mdより）

1. **推測で仕様を埋めない** - 不明点は `docs/spec/DESIGN_SPEC_v0.3.md` を参照
2. **既存データを破壊しない** - 物理削除ではなくsoft delete（is_active=False）
3. **金額と時間は再現可能** - スナップショット、版管理、締めの固定
4. **締め解除は慎重に** - ガードレール（回数上限、二者承認、監査ログ）
5. **ドキュメント更新** - 作業内容を `docs/IMPLEMENTATION_LOG.md` に追記

---

## 💡 ヒント

### CSV取り込みが失敗する場合

1. エンコーディング確認: `kintone_app/*_sjis.csv` を使用
2. フィールドコード確認: `extract_kintone_fields.py` で英語化されているか確認
3. ログ確認: `import_master_data.py` のエラーメッセージを読む

### Kintone同期が遅い場合

- 1アプリずつテストする（全20アプリ一括は避ける）
- APIレート制限に注意（60秒/1000リクエスト）
- バッチサイズを調整（100件ずつなど）

### 請求書PDFが生成されない場合

1. wkhtmltopdf確認: `wkhtmltopdf --version`
2. テンプレート確認: `src/services/pdf_generator.py` のパス
3. ストレージ確認: `storage/invoices/` フォルダが存在するか

---

**このドキュメント作成日**: 2026年1月28日  
**前セッション完了レポート**: `docs/kintone/FIELD_CODE_FINAL_REPORT.md`  
**全体進捗**: Kintone環境構築完了、実装フェーズ開始可能
