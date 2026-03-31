# PROJECT_BOOTSTRAP

## 1. 推奨リポジトリ構成（最小）
- docs/
  - spec/
    - DESIGN_SPEC_v0.3.md
    - REVIEW_MERGE_v0.3.md
  - decisions/
    - DECISION_LOG.md
  - runbook/
    - RUNBOOK_MONTHLY.md
    - RUNBOOK_WEEKLY.md
  - templates/
    - EMAIL_TEMPLATES.md
  - index.md
- db/
  - schema.sql
  - migrations/
- src/
  - (API/バッチ/UI などスタックに合わせて作成)
- scripts/
  - import_csv
  - generate_invoice
  - generate_payout

## 2. 最初のコミットで入れるファイル
- AGENTS.md
- docs/spec/DESIGN_SPEC_v0.3.md
- docs/spec/REVIEW_MERGE_v0.3.md
- docs/decisions/DECISION_LOG.md
- docs/runbook/RUNBOOK_MONTHLY.md
- docs/runbook/RUNBOOK_WEEKLY.md
- docs/templates/EMAIL_TEMPLATES.md
- TASK_BACKLOG.md

## 3. 進行手順（最短）
1 DBスキーマ案の作成
2 CSV取り込みの仕様確定（洗い替えモード含む）
3 取り込みバッチ実装
4 請求の版管理とPDF保管
5 支払明細
6 締めと締め解除ガードレール
7 ダッシュボード
8 権限
9 RUNBOOKで月次運用リハーサル

