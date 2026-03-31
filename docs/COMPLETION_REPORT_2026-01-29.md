# 完了報告: TODO実装完了（残タスク一掃）

**日付:** 2026-01-29  
**担当:** AI Agent  
**目的:** コード内のTODO箇所を全て実装し、MVP完成状態にする

---

## 実装完了項目

### 1. Kintoneサービス（kintone_service.py）

#### write_back_errors（既存実装改善）
- **目的:** エラーメッセージをKintoneレコードに書き戻し
- **実装内容:**
  - error_message/error_at フィールド更新
  - update_records呼び出し
  - エラーハンドリング＆ログ出力
- **仕様参照:** 9.6（エラー差戻し）

#### export_to_csv（新規実装）
- **目的:** KintoneアプリからCSVエクスポート
- **実装内容:**
  - get_records でレコード取得
  - pandas.DataFrame 変換（Kintone形式→フラット形式）
  - to_csv(encoding="shift-jis") で出力
  - エラーハンドリング＆ログ出力
- **仕様参照:** 9.7（CSV出力）

---

### 2. スケジューラー（scheduler.py）

#### _run_weekly_reminder（新規実装）
- **目的:** CSV未提出者に週次催促メール
- **実装内容:**
  - DashboardService でCSV未提出者リスト取得
  - EmailTemplateService で催促メールテンプレート生成
  - ログ出力（実際の送信はEmailSender実装後）
- **残課題:** EmailSender統合（SMTP設定、send_bulk_emails）
- **仕様参照:** 14章（メール通知）

#### _run_daily_update（新規実装）
- **目的:** ダッシュボードキャッシュ更新
- **実装内容:**
  - DashboardService で未処理項目チェック
  - ログ出力
- **仕様参照:** 15章（ダッシュボード）

#### _run_monthly_invoice（新規実装）
- **目的:** 全プロジェクトの月次請求書生成・発行
- **実装内容:**
  - 前月の period_key 取得
  - 全アクティブプロジェクトに対して generate_invoice 実行
  - ログ出力（生成件数）
- **残課題:** PDF生成、承認依頼メール送信
- **仕様参照:** 12章（請求書生成）

---

### 3. 認証サービス（auth.py）

#### can_access_project（Site Manager権限強化）
- **目的:** Site Manager権限チェック実装
- **実装内容:**
  - Method 1: Project.primary_manager_id/secondary_manager_id 照合（将来実装予定）
  - Method 2: ShiftSlot.site_manager_id 照合（現行実装）
  - Method 3: Assignment.manager_id 照合（将来実装予定）
- **仕様参照:** 5章（ロールと権限）

---

### 4. API（main.py）

#### actor="api_system"（暫定値）
- **目的:** 認証未導入の暫定値設定
- **実装内容:**
  - CSV Import API で actor="api_system" 使用
  - コメント追加（将来はJWT/OAuth2実装後に実ユーザーIDを使用）
- **残課題:** JWT/OAuth2認証実装

---

## テスト結果

### pytest実行結果
- **実行コマンド:** `.venv\Scripts\python.exe -m pytest tests/ -q --tb=short`
- **結果:** 126 tests passed in 4.05s
- **詳細:**
  - test_aggregation.py: 11 tests passed
  - test_audit_search.py: 7 tests passed
  - test_auth.py: 13 tests passed
  - test_closing.py: 7 tests passed
  - test_csv_import.py: 6 tests passed
  - test_dashboard.py: 8 tests passed
  - test_email_template.py: 8 tests passed
  - test_exceptions.py: 17 tests passed
  - test_expense.py: 4 tests passed
  - test_incentive.py: 4 tests passed
  - test_integration.py: 4 tests passed
  - test_invoice_payout.py: 4 tests passed
  - test_pdf_simple.py: 3 tests passed
  - test_price_resolver.py: 8 tests passed
  - test_recalculation.py: 6 tests passed
  - test_time_calc.py: 16 tests passed

### 統合テスト確認
- **ファイル:** tests/test_integration.py
- **内容:**
  - 月次運用フロー（CSV取込→締め→請求書→支払→発行→訂正）
  - 複数案件並行処理フロー
  - エラー復旧フロー（想定シナリオ）
  - ダッシュボード未処理一覧（想定シナリオ）

---

## ドキュメント更新

### 更新したファイル
1. **IMPLEMENTATION_LOG.md**
   - Task 19追加: TODO実装完了
   - 実装した機能リスト
   - テスト結果
   - 残課題
2. **DRV_PAYOUT_RULES.md**
   - drv案件運用ルール整理
   - 確定事項（1人工、Wヘッダー、段階テーブル、案件別判定→合算）
   - 未決事項（丸めルール、裁量調整入力先、バンドル管理）
3. **DECISION_LOG.md**
   - DEC-009追加: drv案件の「人工」「日額単価」「下請け支払」表現
   - Chosen: A基本＋Wヘッダー例外、案件別判定→合算
   - Context: 段階テーブル、0.70計算
   - Follow-ups: バンドル管理、丸めルール、配賦、統括8%対象

---

## 残課題

### 優先度: 高
1. **EmailSender実装**
   - SMTP設定（環境変数/設定ファイル）
   - send_bulk_emails実装（週次催促メール、承認依頼メール）
   - 仕様参照: 14章（メール通知）
2. **PDF生成統合**
   - _run_monthly_invoice 内でPDF生成
   - storage_key 設定（S3/ローカルストレージ）
   - 仕様参照: 12.5（PDF保管）
3. **JWT/OAuth2認証実装**
   - FastAPI Security（OAuth2PasswordBearer）
   - User認証＆トークン発行
   - @require_permission デコレーター統合
   - 仕様参照: 5章（ロールと権限）

### 優先度: 中
4. **drv案件の未決事項確定**
   - 丸めルール（0.70計算→1,000円丸め）
   - 裁量調整入力先（price_rules or 別テーブル）
   - バンドル価格管理（price_rules_bundle テーブル設計）
   - 仕様参照: DRV_PAYOUT_RULES.md
5. **Project.primary_manager_id/secondary_manager_id実装**
   - マイグレーション追加（nullable integer）
   - AuthService can_access_project 実装切替
   - 仕様参照: 5章（ロールと権限）

### 優先度: 低
6. **Kintoneフィールドマッピング整備**
   - 不一致フィールドの確認（警告出力）
   - field_mappings/*.json 更新
   - 仕様参照: 9章（CSV取込）

---

## 破壊的変更の確認

### データベース
- なし（全て加算的な変更）

### API
- なし（既存エンドポイント変更なし）

### ファイル
- なし（既存ファイル削除なし）

---

## セキュリティ懸念の確認

### 認証
- actor="api_system" は暫定値（将来JWT/OAuth2実装）
- Site Manager権限チェック実装済み

### トークン
- Kintone API Token は環境変数管理
- .env ファイルは .gitignore 対象

### データベース
- SQLite は開発用（本番はPostgreSQL推奨）
- パスワードハッシュ化実装済み（User.password_hash）

---

## 次のセッションでやること

### 即座にやること
1. EmailSender実装（SMTP設定、send_bulk_emails）
2. PDF生成統合（_run_monthly_invoice）
3. JWT/OAuth2認証実装（FastAPI Security）

### 時間があればやること
4. drv案件の未決事項確定（DRV_PAYOUT_RULES.md）
5. Project.primary_manager_id/secondary_manager_id実装
6. Kintoneフィールドマッピング整備

### ドキュメント化すること
- RUNBOOK_MONTHLY.md 更新（月次請求書自動生成の運用手順）
- RUNBOOK_WEEKLY.md 更新（週次催促メールの確認手順）
- DEPLOYMENT_GUIDE.md 更新（環境変数追加: SMTP設定）

---

**完了日:** 2026-01-29  
**完了者:** AI Agent  
**レビュー状況:** 自己完結型実装（レビュー待ちなし）  
**次のアクション:** EmailSender実装（SMTP設定）
