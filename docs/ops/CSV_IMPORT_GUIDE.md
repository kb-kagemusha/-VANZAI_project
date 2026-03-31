# CSV取り込み運用ガイド

**対象**: 運用担当者（ops権限）  
**仕様参照**: DESIGN_SPEC_v0.3.md セクション9章

---

## 📋 概要

実績CSV（kintoneエクスポート）をシステムに取り込む手順と、エラー対応方法を記載します。

---

## 🔄 取り込みモード

### 1. 追記モード（append）
- **用途**: 新規データの追加
- **動作**: 既存データはそのまま、新規行のみ追加
- **リスク**: 重複データの検知は file_hash のみ

### 2. 洗い替えモード（replace）
- **用途**: 時刻修正、キャンセル反映
- **動作**: 指定範囲（period_key × project × worker）の既存データを無効化してから投入
- **リスク**: 範囲外データも誤って無効化する可能性

### 3. マージモード（merge）
- **用途**: 部分更新
- **動作**: 不変キー（shift_label等）で同一行を判定し、差分のみ更新
- **リスク**: 未対応（Phase 2予定）

---

## 📥 取り込み手順

### ステップ1: CSVエクスポート（kintone）
1. kintoneアプリ「実績管理」を開く
2. 対象期間をフィルタ（例: 2026年1月）
3. 「ファイルに書き出す」→「CSV」
4. 文字コード: **Shift-JIS**（Excelで開く場合）
5. ファイル名: `actuals_YYYYMM.csv`（例: `actuals_202601.csv`）

### ステップ2: ファイル配置
```bash
# 取り込みディレクトリに配置
cp actuals_202601.csv /path/to/import/

# ファイルハッシュを確認（重複検知用）
sha256sum actuals_202601.csv
```

### ステップ3: 取り込み実行
```python
from src.services.csv_import import import_actuals_csv
from sqlalchemy.orm import Session

session = Session()

result = import_actuals_csv(
    session=session,
    file_path="actuals_202601.csv",
    project_id="01ABC123...",  # 対象プロジェクトID
    period_key="202601",        # 対象期間（YYYYMM）
    mode="append",              # または "replace"
    submitted_by="ops_user"     # 実行者
)

if result.success:
    print(f"成功: {result.count_success}件")
else:
    print(f"エラー: {result.errors}")
```

### ステップ4: 確認
```sql
-- 取り込み件数確認
SELECT COUNT(*) FROM actuals 
WHERE period_key = '202601' 
  AND import_batch_id = '01XYZ...';

-- エラー確認
SELECT * FROM import_batches 
WHERE period_key = '202601' 
ORDER BY created_at DESC 
LIMIT 1;
```

---

## ⚠️ エラー対応

### エラー1: 重複ファイル
```
DuplicateImportException: File hash already exists
```

**原因**: 同じCSVを再度取り込もうとした

**対応**:
1. 既に取り込み済みか確認
   ```sql
   SELECT * FROM import_batches WHERE file_hash = 'sha256...';
   ```
2. 意図的な再取り込みの場合は、洗い替えモードを使用
   ```python
   mode="replace"  # 既存データを無効化してから取り込み
   ```

### エラー2: キャンセル済みアサイン
```
AssignmentCanceledException: Cannot import to canceled assignment
```

**原因**: キャンセル済みのシフト枠に実績を登録しようとした

**対応**:
1. kintoneでアサインステータスを確認
2. 不要な実績行をCSVから削除
3. または、Assignment.statusを確認して修正
   ```sql
   UPDATE assignments SET status = 'confirmed' 
   WHERE id = '01ABC...' AND cancel_reason IS NULL;
   ```

### エラー3: 必須カラム不足
```
InvalidCSVFormatException: Missing required column: work_date
```

**原因**: CSV形式が不正

**対応**:
1. CSVヘッダーを確認
   ```csv
   work_date,worker_id,project_id,start_time,end_time,...
   ```
2. kintoneエクスポート設定を確認
3. 手動編集時の列削除ミスをチェック

### エラー4: データ型不一致
```
ValidationException: Invalid date format: 2026/01/10
```

**原因**: 日付フォーマットが不正

**対応**:
- 期待形式: `2026-01-10`（ISO 8601）
- Excel変換時に注意（`2026/1/10` → `2026-01-10`）

---

## 🔍 トラブルシューティング

### 問題: 取り込み後に金額が0円
**原因**: 単価マスタが未登録

**診断**:
```sql
-- 単価マスタ確認
SELECT * FROM price_sales 
WHERE project_id = '01ABC...' 
  AND role_id = '01DEF...'
  AND valid_from <= '2026-01-10'
  AND (valid_to IS NULL OR valid_to >= '2026-01-10');
```

**対応**:
1. 単価マスタを登録
   ```sql
   INSERT INTO price_sales (project_id, role_id, unit_price, valid_from)
   VALUES ('01ABC...', '01DEF...', 1500.00, '2026-01-01');
   ```
2. 再計算を実行
   ```python
   from src.services.recalculation import execute_recalculation
   execute_recalculation(session, project_id, period_key, user_id, force=False)
   ```

### 問題: 実績が2重に表示される
**原因**: 洗い替えモードの範囲設定ミス

**診断**:
```sql
-- 同一日×稼働者の実績を確認
SELECT work_date, worker_id, COUNT(*) 
FROM actuals 
WHERE period_key = '202601' AND status = 'active'
GROUP BY work_date, worker_id 
HAVING COUNT(*) > 1;
```

**対応**:
1. 重複分を無効化
   ```sql
   -- 古い方を無効化（created_atで判定）
   UPDATE actuals SET status = 'invalid', invalid_reason = '重複データ'
   WHERE id IN (
     SELECT id FROM (
       SELECT id, ROW_NUMBER() OVER (
         PARTITION BY work_date, worker_id 
         ORDER BY created_at DESC
       ) as rn
       FROM actuals WHERE period_key = '202601'
     ) t WHERE rn > 1
   );
   ```

### 問題: 取り込みが途中で止まる
**原因**: トランザクションタイムアウト、メモリ不足

**対応**:
1. ファイルを分割（月を週単位に分割）
2. チャンク処理を有効化（未対応の場合は Phase 2 待ち）

---

## 📊 洗い替えモード詳細

### 無効化範囲
洗い替えモードでは以下の条件の実績が無効化されます：

```python
# 無効化対象
WHERE period_key = :period_key      # 同一期間
  AND project_id = :project_id      # 同一プロジェクト
  AND worker_id IN (SELECT DISTINCT worker_id FROM 新規CSV)  # CSV内の稼働者
  AND status = 'active'             # 有効な実績のみ
```

### 実行例
```python
# 2026年1月の実績を洗い替え
result = import_actuals_csv(
    session=session,
    file_path="actuals_202601_corrected.csv",
    project_id="01ABC123...",
    period_key="202601",
    mode="replace",  # 洗い替え
    submitted_by="ops_user"
)

# 無効化された実績を確認
invalid_count = session.query(Actual).filter(
    Actual.period_key == "202601",
    Actual.status == "superseded",  # 洗い替えで無効化
    Actual.invalid_reason == "Replaced by new import"
).count()

print(f"無効化: {invalid_count}件")
print(f"新規投入: {result.count_success}件")
```

---

## 🔐 権限
CSV取り込みには **IMPORT_ACTUAL** 権限が必要です。

**保有ロール**:
- admin
- ops

---

## 📝 監査ログ
すべての取り込みは `import_batches` テーブルに記録されます。

```sql
-- 最近の取り込み履歴
SELECT 
    created_at,
    file_name,
    period_key,
    submitted_by,
    status,
    count_success,
    count_error
FROM import_batches
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🚨 緊急時対応

### 誤った取り込みのロールバック
```python
from src.services.csv_import import rollback_import

# インポートバッチIDを指定
rollback_import(
    session=session,
    import_batch_id="01XYZ...",
    user_id="admin_user"
)

# 実行内容:
# 1. 該当バッチの全実績を status='invalid' に変更
# 2. import_batches.status を 'rolled_back' に更新
# 3. 監査ログに記録
```

### データ整合性チェック
```sql
-- 1. 実績の整合性確認
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
    SUM(CASE WHEN applied_price_sales IS NULL THEN 1 ELSE 0 END) as missing_price
FROM actuals
WHERE period_key = '202601';

-- 2. 孤立実績の確認
SELECT a.id, a.work_date, a.worker_id
FROM actuals a
LEFT JOIN assignments asn ON a.assignment_id = asn.id
WHERE asn.id IS NULL;

-- 3. キャンセル済みアサインの実績確認
SELECT a.id, asn.status, asn.cancel_reason
FROM actuals a
JOIN assignments asn ON a.assignment_id = asn.id
WHERE asn.status = 'canceled' AND a.status = 'active';
```

---

## 📞 サポート
CSV取り込みでエラーが解決しない場合は、以下を添えて開発チームに連絡：

1. エラーメッセージ全文
2. import_batch_id
3. CSVファイル（先頭10行）
4. 実行したコマンド

---

**更新履歴**:
- 2026-01-27: 初版作成
