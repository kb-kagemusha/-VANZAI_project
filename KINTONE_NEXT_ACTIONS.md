# Kintone実装: 次の具体的アクション

**作成日**: 2026年1月28日  
**現在地**: suppliers再作成・同期完了 → 運用準備完了

---

## ✅ 完了済み（2026-01-30）

### 実施内容

* suppliersアプリをゲストスペースに作成（app_id=199）
* suppliersフィールドのコード補正（scripts/add_kintone_missing_fields.py）
* 不要フィールド削除
* suppliers同期（初回 add）完了

### 同期実行（完了）
```powershell
python scripts/sync_db_to_kintone.py suppliers --mode add
```

**確認**:
```powershell
sqlite3 vanzai.db "SELECT name, COUNT(*) FROM (
  SELECT 'workers' as name, COUNT(*) as cnt FROM workers
  UNION ALL SELECT 'clients', COUNT(*) FROM clients
  UNION ALL SELECT 'sites', COUNT(*) FROM sites
  UNION ALL SELECT 'roles', COUNT(*) FROM roles
  UNION ALL SELECT 'project_types', COUNT(*) FROM project_types
) GROUP BY name;"
```

**期待結果**:
```
workers|10
clients|3
sites|5
roles|3
project_types|3
```

---

### 補足
* `scripts/sync_db_to_kintone.py` は既に運用中
* suppliersの初回投入は `--mode add` を使用

---

## 📋 完了状況

* DB準備: 完了
* CSV取り込み: 完了
* 同期スクリプト: 完了
* 動作確認: 完了
* ドキュメント更新: 完了

---

## 🚧 想定される障害と対処法

### 障害1: import_master_data.py が存在しない

**症状**:
```powershell
python scripts/import_master_data.py workers
# FileNotFoundError
```

**対処法**:
1. `scripts/` フォルダを確認
2. スクリプトが存在しない場合は作成:
   ```powershell
   # CSVからDBへの取り込みスクリプトを作成
   # pandas + SQLAlchemy を使用
   ```

### 障害2: CSVファイルが見つからない

**症状**:
```
FileNotFoundError: kintone_app/workers_sjis.csv
```

**対処法**:
1. CSVファイル存在確認
   ```powershell
   ls kintone_app/*_sjis.csv
   ```
2. ファイル名が異なる場合は `workers_utf8.csv` 等を確認
3. 必要に応じてエンコーディング変換

### 障害3: Kintone APIエラー（401 Unauthorized）

**症状**:
```
401 Unauthorized - Invalid API token
```

**対処法**:
1. `.env` ファイルでトークン確認
   ```powershell
   cat .env | grep KINTONE_TOKEN_WORKERS
   ```
2. トークンが空の場合、`アプリTOKEN一覧.csv` から取得
3. `.env` に設定:
   ```
    KINTONE_TOKEN_WORKERS=<SET_IN_ENV>
   ```

※ セキュリティのため、APIトークンはリポジトリにコミットしない（漏えいの可能性がある場合はトークン再生成/ローテーション推奨）

### 障害4: フィールドコードエラー

**症状**:
```
KeyError: 'ドロップダウン' field not found
```

**対処法**:
1. フィールドコード確認
   ```powershell
   python scripts/extract_kintone_fields.py 165
   ```
2. 日本語フィールドが残っている場合は再変換
   ```powershell
   python scripts/update_all_field_codes.py workers --yes
   ```

---

## 📊 進捗の可視化

### 現在の状態（2026-01-28 13:30）

```
[====================================] 40% 完了

✅ 完了:
- DB設計・マイグレーション
- モデル・サービス層実装
- REST API実装
- テスト（126件全成功）
- Kintone環境構築
- フィールドコード統一（全20アプリ）
- APIトークン設定（全20アプリ）

🔄 進行中:
- CSV取り込み（マスタ5アプリ）
- DB ↔ Kintone 双方向同期

⏳ 未着手:
- トランザクションデータ投入
- 集計・請求書生成テスト
- 月次運用フロー実証
- 本番データ移行
- ユーザートレーニング
```

### 次のマイルストーン

| マイルストーン | 期日目安 | 完了条件 |
|-------------|---------|---------|
| データ投入完了 | +2時間 | 全20アプリのデータがDB+Kintoneに存在 |
| 請求書生成成功 | +4時間 | PDF生成、Kintone出力確認 |
| 月次運用実証 | +8時間 | 締め→請求→支払の一連フロー完遂 |
| 本番稼働準備完了 | +2日 | 実データ移行、権限設定、監視体制 |

---

## 🎯 今日中に達成すべきゴール

**ゴール**: マスタ5アプリのデータがDBとKintone両方に存在する状態

**成功基準**:
1. SQLiteで `SELECT COUNT(*) FROM workers;` → 10件
2. Kintone UIで稼働者マスタを開く → 10件表示
3. データの整合性確認（worker_id, name等が一致）

**達成後のメリット**:
- 以降のトランザクションデータ投入がスムーズ
- 外部キー制約が機能（データ品質向上）
- 運用フロー実証の土台が整う

---

## 📝 作業ログテンプレート

作業後に `docs/IMPLEMENTATION_LOG.md` に追記：

```markdown
## 2026-01-28: Kintone CSV取り込み・DB同期

### 実施内容
- マスタ5アプリのCSV取り込み実行
- DB → Kintone 同期スクリプト作成
- workers アプリで動作確認

### 結果
- ✅ workers: 10件取り込み成功、Kintone同期確認
- ✅ clients: 3件取り込み成功
- ✅ sites: 5件取り込み成功
- ✅ roles: 3件取り込み成功
- ✅ project_types: 3件取り込み成功

### 課題
- [ ] 他15アプリの同期スクリプト実装
- [ ] トランザクションデータ取り込み手順確立

### 次のステップ
- トランザクション10アプリのCSV取り込み
- 請求書生成テスト準備
```

---

**所要時間見積もり**: 30分～1時間  
**推奨実施時間**: 今すぐ（依存なし、環境準備完了済み）  
**参照ドキュメント**: [NEXT_SESSION_KINTONE.md](NEXT_SESSION_KINTONE.md)
