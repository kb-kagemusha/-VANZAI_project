# テスト修正サマリー

## 現在のステータス: 49/67 PASS (73%)

## 残存エラー分類

### 1. SQLite型エラー (7件)
- **エラー**: `SQLite Time type only accepts Python time objects as input`
- **原因**: start_time/end_timeに文字列("09:00")を渡している
- **修正**: `from datetime import time` して `time(9, 0)` を使用
- **該当テスト**:
  - test_dashboard.py: test_get_unprocessed_items, test_get_variance_alerts
  - test_invoice_payout.py: test_generate_invoice_basic, test_generate_payout_basic
  - test_integration.py: test_full_monthly_workflow, test_multi_worker_workflow (一部)

### 2. ShiftSlot.role_id エラー (2件)
- **エラー**: `'role_id' is an invalid keyword argument for ShiftSlot`
- **原因**: test_integration.pyの残り箇所でrole_idを使用
- **修正**: role_idを削除
- **該当テスト**:
  - test_integration.py: test_full_monthly_workflow, test_multi_worker_workflow

### 3. Expense.receipt_url エラー (4件)
- **エラー**: `'receipt_url' is an invalid keyword argument for Expense`
- **原因**: Expenseモデルにreceipt_urlフィールドが存在しない
- **修正**: expense_service.pyでreceipt_url削除、またはモデルに追加
- **該当テスト**: test_expense.py全4件

### 4. Incentive.calculation_json エラー (2件)
- **エラー**: `'calculation_json' is an invalid keyword argument for Incentive`
- **原因**: incentive_service.pyがcalculation_jsonを使用
- **修正**: incentive_service.pyでcalculation_json削除
- **該当テスト**: test_incentive.py: test_create_incentive, test_approve_incentive

### 5. ImportBatch.file_hash NOT NULL制約 (2件)
- **エラー**: `NOT NULL constraint failed: import_batches.file_hash`
- **原因**: file_hashがNOT NULLだがテストで指定していない
- **修正**: file_hash="dummy_hash"を追加
- **該当テスト**: test_incentive.py: test_match_attendance_incentive, test_match_attendance_incentive_not_enough

### 6. Assignment.shift_slot.work_date SQLAlchemyエラー (2件)
- **エラー**: `Assignment.shift_slot has an attribute 'work_date'`
- **原因**: dashboard.pyで不正なSQLAlchemyクエリ構文
- **修正**: ShiftSlot.work_dateを直接参照するクエリに変更
- **該当テスト**: test_dashboard.py: test_unprocessed_invoices, test_unprocessed_payouts

### 7. Closing.is_soft_closed属性エラー (2件)
- **エラー**: `'Closing' object has no attribute 'is_soft_closed'`
- **原因**: テストがis_soft_closed/is_hard_closedプロパティを期待
- **修正**: Closingモデルに@propertyを追加、またはtest_closing.py修正
- **該当テスト**: test_closing.py: test_get_closing_status, test_dashboard.py: test_get_closing_status

## 優先修正順序

1. start_time/end_timeを time() オブジェクトに変更 (最多7件)
2. Expense/Incentiveのフィールド整合 (6件)
3. test_integration.pyのrole_id削除 (2件)
4. ImportBatch.file_hash追加 (2件)
5. dashboard.pyのクエリ修正 (2件)
6. Closingプロパティ追加 (2件)

## 次のアクション

1-6の修正を順番に実施して67/67 PASS達成
