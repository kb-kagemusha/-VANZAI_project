# ファイルインデックス（File Index）

## 目的
VANZAIプロジェクトの全ファイルの役割と依存関係を一覧化

## 最新更新（2026-02-17）

以下は直近の運用変更で、既存セクションより優先して参照する。

- App174フロント発行導線を更新
  - 「請求書発行」→「見積書・請求書の発行」へ改名
  - 「登録」行から「確認」行へ移動
  - 支払明細発行対象に「紹介者」を追加
- App165稼働者の経由先を `via_destination` に統一
  - 選択肢: `下請け` / `紹介` / `VANZAI直接`
  - `VANZAI直接` 時は「紹介者/下請け」を空欄化・入力不可
- データ移行
  - `group -> via_destination` 移行は完了済み
  - `scripts/migrate_workers_via_destination.py` は一回限り移行用（通常運用では非使用）
- App173（支払明細）スキーマ是正
  - 正規フィールドを追加（`payout_id` / `worker_id` / `project_id` / `closed_at` など）
  - 旧ラジオ/日時フィールドを `【旧】...` ラベル化
- App171/App173 legacy削除
  - `【旧】` ラベル項目を物理削除
- App171/App173 フォーム順最適化
  - 正規フィールドを先頭へ再配置
- App171 旧由来コード削除
  - `数値* / 日付 / 日時* / 文字列__1行_*` を物理削除
- App174 稼働者一覧絞り込み強化
  - 経由先/紹介者を選択式で絞り込み可能に更新
- App174 稼働者参照の堅牢化
  - App165のフィールドコード差異を自動解決して表示/保存を統一
- App174 稼働者参照アプリの修正
  - `CONFIG.apps.workers` を `312` から `165`（稼働者マスタ）へ修正
- ドキュメント残タスクを完了
  - ユーザー向けマニュアルを追加
  - FAQを追加
  - RUNBOOK整合確認ログを追加
- App174 見積書PDFの自動生成・添付を実装
  - 見積書発行後にApp171レコード詳細へ遷移
  - ブラウザ側でPDF生成（jsPDF）→ App171 FILEフィールドへ添付
  - App171にFILEフィールドがない場合は `invoice_pdf` を追加して対応
- PDFアップロード認証エラー（CB_JH01）を是正
  - アップロード処理を `XMLHttpRequest` 化
  - `X-Requested-With: XMLHttpRequest` を付与
- PDFアップロードのトークン失効（CB_CS01）を是正
  - `csrf.json` でトークン再取得 → 1回自動リトライ
  - 失敗時は再読み込み案内付きエラーダイアログを表示
- App174 見積書PDFのレイアウト/保存方式を更新
  - Canvas画像埋め込み方式を廃止し、jsPDFのテキスト描画へ変更（軽量化）
  - 既定の保存先を `download`（ローカル保存）へ変更
  - 保存先を `CONFIG.invoicePdf.uploadTarget` で切替可能化（`download` / `external` / `kintone`）
  - `external` 用のアップロード拡張点（`externalUploadUrl`）を追加

関連ファイル:
- `kintone_app/customizations/front_dashboard.js`
- `docs/kintone/FRONT_DASHBOARD_SETUP.md`
- `docs/IMPLEMENTATION_LOG.md`
- `scripts/migrate_workers_via_destination.py`
- `scripts/fix_app173_payout_schema.py`
- `scripts/delete_legacy_fields_171_173.py`
- `scripts/reorder_layout_171_173.py`
- `scripts/delete_obsolete_fields_app171.py`
- `docs/ops/USER_MANUAL.md`
- `docs/ops/FAQ.md`
- `docs/ops/RUNBOOK_VALIDATION_2026-02-16.md`
- `scripts/ensure_app171_pdf_file_field.py`

追加（2026-02-17 夜）:
- `kintone_app/customizations/front_dashboard.js`（PDF軽量化・保存先切替・CSRF複数トークン試行）

---

## ディレクトリ構造

```
VANZAI_project/
├── docs/                   # ドキュメント
│   ├── spec/              # 仕様書
│   ├── decisions/         # 設計決定ログ
│   ├── kintone/           # Kintone連携ドキュメント
│   ├── ops/               # 運用ドキュメント
│   └── IMPLEMENTATION_LOG.md  # 実装ログ
├── src/                   # ソースコード
│   ├── models/            # データモデル
│   └── services/          # ビジネスロジック
├── tests/                 # テストコード
├── alembic/              # DBマイグレーション
│   └── versions/         # マイグレーションスクリプト
└── kintone_app/          # Kintone CSVサンプル
```

---

## コアファイル

### ルートディレクトリ

| ファイル | 目的 | 依存 |
|---------|------|------|
| README.md | プロジェクト概要、セットアップ手順 | - |
| pyproject.toml | Python依存関係、プロジェクト設定 | - |
| alembic.ini | Alembic設定（DB接続、マイグレーション） | - |
| .env.example | 環境変数テンプレート | - |
| **.env** | **環境変数設定（2026-01-27作成）** | - |
| AGENTS.md | AI Agent用の実装指示書 | - |
| PROJECT_BOOTSTRAP.md | プロジェクト初期セットアップガイド | - |
| DEPLOYMENT_GUIDE.md | デプロイメント8ステップ詳細手順 | - |
| NEXT_SESSION_INSTRUCTIONS.md | 次セッション用AI Agent指示 | - |
| RUNBOOK_MONTHLY.md | 月次運用手順書 | - |
| RUNBOOK_WEEKLY.md | 週次運用手順書 | - |
| TASK_BACKLOG.md | 完了済みバックログ（計画履歴） | - |
| **vanzai.db** | **SQLiteデータベース（2026-01-27作成、458KB）** | - |

---

## ドキュメント (docs/)

### 完了レポート

| ファイル | 目的 | 作成日 |
|---------|------|--------|
| COMPLETION_REPORT.md | 実装完了レポート（タスクA〜H） | 2026-01-27 |
| TASK_COMPLETION_2026-01-27.md | 全8タスク完了レポート | 2026-01-27 |
| **DEPLOYMENT_COMPLETION_2026-01-27.md** | **デプロイメント完了レポート** | **2026-01-27** |
| TEST_FIX_SUMMARY.md | テスト修正サマリー | 2026-01-27 |
| IMPLEMENTATION_LOG.md | 実装ログ | - |

### 仕様書 (docs/spec/)

| ファイル | 目的 | セクション |
|---------|------|-----------|
| DESIGN_SPEC_v0.3.md | **正本仕様書** (778行) | 1-27章、全機能の詳細設計 |
| REVIEW_MERGE_v0.3.md | レビュー反映履歴 | 仕様変更の根拠 |
| CHANGELOG_v0.3_2026-01-27.md | 変更履歴 | バージョン管理 |

### 設計決定 (docs/decisions/)

| ファイル | 目的 |
|---------|------|
| DECISION_LOG.md | 設計決定の記録（DEC-001〜） |

### Kintone連携 (docs/kintone/)

| ファイル | 目的 | 作成日 |
|---------|------|--------|
| KINTONE_APPS_LIST.md | Kintoneアプリ一覧 | 2026-01-27 |
| KINTONE_SETUP_GUIDE.md | Kintone連携セットアップ | 2026-01-27 |
| PROJECTS_REQUEST_FIELDS.md | 案件依頼サンプル→案件マスタのマッピング | 2026-02-03 |
| **FIELD_CODE_FINAL_REPORT.md** | **フィールドコード統一 最終完了レポート（全20アプリ、166フィールド）** | **2026-01-28** |
| **FIELD_CODE_COMPLETION_REPORT.md** | **フィールドコード統一完了レポート（第3フェーズまで）** | **2026-01-28** |
| **FIELD_CODE_CONVERSION.md** | **フィールドコード英語化の全記録** | **2026-01-28** |
| **REQUIRED_APPS_FIELDS.md** | **必要アプリのフィールド定義（equipment, tasks等）** | **2026-01-28** |
| FIELD_CODE_SETUP.md | フィールドコード設定の3つの方法 | 2026-01-27 |
| AUTO_SETUP_GUIDE.md | 自動化セットアップガイド | 2026-01-27 |
| FIELD_TYPE_ISSUE.md | ドロップダウン/ラジオボタン制約説明 | 2026-01-27 |
| MANUAL_FIELD_TYPE_CHANGE.md | 手動フィールドタイプ変更ガイド | 2026-01-27 |
| MISSING_APPS.md | invoices/payouts作成要件 | 2026-01-27 |
| FIELD_CODE_COMPLETE.md | 第1グループ完了報告 | 2026-01-27 |
| csv/*.csv | Kintone用CSVサンプル | - |

### 運用 (docs/ops/)

| ファイル | 目的 |
|---------|------|
| STATUS.md | 現在の実装状況 |
| TASK_BACKLOG.md | 完了済みバックログ（docs/用） |
| CSV_IMPORT_GUIDE.md | CSV取り込みガイド |
| IMPLEMENTATION_REPORT_2026-01-27.md | 実装レポート |
| DRV_PAYOUT_RULES.md | drv案件の稼働実績→支払/請求ルール整理（案） |
| V_BILLING_PAYOUT_MATRIX.md | V：請求/支払対応表（参照用） | 2026-02-02 |
| USER_MANUAL.md | ユーザー向け運用マニュアル（Ops/Accounting/Admin向け） |
| FAQ.md | 運用・Kintone連携FAQ |
| RUNBOOK_VALIDATION_2026-02-16.md | RUNBOOK整合確認ログ（2026-02-16） |

---

## スクリプト (scripts/)

| ファイル | 目的 | 状態 |
|---------|------|------|
| **import_master_data.py** | **初期マスタデータ投入（2026-01-27修正済み）** | ✅ 動作確認済み |
| scheduler_runner.py | スケジューラー実行スクリプト | 未使用 |
| fix_app173_payout_schema.py | App173（支払明細）の型是正・旧項目レガシー化 | ✅ 2026-02-17 実行済み |
| delete_legacy_fields_171_173.py | App171/App173の `【旧】` 項目削除 | ✅ 2026-02-17 実行済み |
| reorder_layout_171_173.py | App171/App173フォームの並び順最適化 | ✅ 2026-02-17 実行済み |
| delete_obsolete_fields_app171.py | App171旧由来コード項目の物理削除 | ✅ 2026-02-17 実行済み |

**import_master_data.py 投入データ:**
- クライアント: 2件
- 稼働者: 3件
- ロール: 3件
- 案件タイプ: 2件
- サイト: 2件
- 案件: 1件

---

## API層 (src/api/)

| ファイル | 行数 | 目的 | 状態 |
|---------|------|------|------|
| deps.py | ~30 | DB依存性注入（engine, SessionLocal, get_db） | ✅ 動作確認済み |
| schemas.py | 未確認 | Pydanticスキーマ定義 | - |
| main.py | ~700 | FastAPIメインアプリケーション | ✅ 動作確認済み |
| **main_simple.py** | **~150** | **簡易版APIサーバー（初期動作確認用）** | ✅ 動作確認済み |

**main_simple.py エンドポイント:**
- `GET /` - ルートヘルスチェック
- `GET /api/health` - 詳細ヘルスチェック（DB接続確認）
- `GET /api/dashboard` - ダッシュボード統計
- `GET /api/clients` - クライアント一覧
- `GET /api/workers` - 稼働者一覧
- `GET /api/projects` - 案件一覧

**起動方法:**
```powershell
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Swagger UI:** http://localhost:8000/api/docs

---

## ソースコード (src/)

### モデル層 (src/models/)

| ファイル | 行数 | 目的 | 依存 |
|---------|------|------|------|
| **base.py** | 60 | Base, TimestampMixin, SoftDeleteMixin | sqlalchemy |
| **enums.py** | 250 | 全Enum定義（30種類） | - |
| **master.py** | 288 | マスタデータモデル（Worker, Client, Site, Role, PriceMaster, User, IncentiveRule） | base.py, enums.py |
| **transaction.py** | 820 | トランザクションモデル（Project, ShiftSlot, Assignment, Actual, Invoice, Payout, Expense, Incentive） | base.py, enums.py, master.py |

#### Enumリスト (enums.py)
- AssignmentStatus, ActualStatus, ImportMode, ImportScopeType, ImportBatchStatus
- RoundingMethod, BreakDeductionRule, TimeCalcMode, NightCalcMode
- AuditAction, InvoiceStatus, PayoutStatus, UserRole, Permission
- ClosingStatus, ExpenseStatus, IncentiveStatus

#### Masterモデルリスト (master.py)
- Worker, Client, Site, Role, PriceSales, PriceOutsource, User, IncentiveRule

#### Transactionモデルリスト (transaction.py)
- Project, ShiftSlot, Assignment, ImportBatch
- Actual, Invoice, InvoiceLine, Payout, PayoutLine
- Closing, AuditLog, Expense, Incentive

---

### サービス層 (src/services/)

| ファイル | 行数 | 目的 | 実装形式 | 依存モデル | 依存サービス |
|---------|------|------|---------|-----------|-------------|
| **aggregation.py** | 未確認 | 実績集計（売上/外注費） | 関数 | Actual | - |
| **audit.py** | 未確認 | 監査ログ記録 | クラス | AuditLog | - |
| **closing.py** | 未確認 | 締め処理（Soft/Hard Close） | 関数 | Closing, Actual | audit |
| **csv_import.py** | 713 | CSV取り込み（洗い替え、重複防止） | クラス (CsvImportService) | ImportBatch, Actual | audit |
| **dashboard.py** | 未確認 | ダッシュボード集計 | 関数 (get_dashboard_summary) | Actual, Invoice, Payout | - |
| **invoice_service.py** | 未確認 | 請求書生成・発行 | 関数 | Invoice, InvoiceLine | aggregation, audit |
| **payout_service.py** | 未確認 | 支払明細生成・承認 | 関数 | Payout, PayoutLine | aggregation, audit |
| **price_resolver.py** | 未確認 | 単価解決（有効期間、デフォルト） | 関数 | PriceSales, PriceOutsource | - |
| **time_calc.py** | 未確認 | 時間計算（丸め、休憩、深夜） | 関数 | Actual | - |
| **auth.py** | 266 | 権限管理 | クラス | User | - |
| **recalculation.py** | 417 | 再計算サービス | クラス | Actual | time_calc, price_resolver, audit |
| **expense_service.py** | 291 | 経費精算 | クラス | Expense | audit, auth |
| **incentive_service.py** | 390 | インセンティブ管理 | クラス | Incentive, IncentiveRule | audit, auth |
| **pdf_generator.py** | 320 | PDF生成 | 関数 | Invoice, Payout | reportlab |
| **email_template.py** | 310 | メールテンプレート（7種類） | クラス | - | - |
| **bank_transfer.py** | 未確認 | 銀行振込ファイル生成（全銀フォーマット） | クラス | Payout | - |
| **kintone_service.py** | 未確認 | Kintone API連携（DB→Kintone同期、実績取得、エラー書き戻し） | クラス | - | - |
| **scheduler.py** | 未確認 | スケジューラー（週次/月次ジョブ、env駆動） | クラス | - | email_template |

**重要な実装パターンの違い:**
- **クラス形式:** CsvImportService, AuditService, ExpenseService, IncentiveService, RecalculationService
- **関数形式:** invoice_service.*, payout_service.*, closing.*, dashboard.get_dashboard_summary()
- **API層での注意:** クラスと関数でインポート・使用方法が異なる

---

## テストコード (tests/)

| ファイル | テスト数 | 対象 | 状態 |
|---------|---------|------|------|
| conftest.py | - | pytest設定、fixturedef | - |
| **test_auth.py** | 13 | 権限管理 | ✅ PASS |
| **test_recalculation.py** | 6 | 再計算サービス | ✅ PASS |
| **test_closing.py** | 7 | 締め処理 | ✅ PASS |
| **test_csv_import.py** | 6 | CSV取り込み | ✅ PASS |
| **test_time_calc.py** | 16 | 時間計算 | ✅ PASS |
| **test_invoice_payout.py** | 4 | 請求・支払 | ✅ PASS |
| **test_expense.py** | 4 | 経費精算 | ✅ PASS |
| **test_incentive.py** | 4 | インセンティブ | ✅ PASS |
| **test_aggregation.py** | 11 | 集計サービス | ✅ PASS |
| **test_dashboard.py** | 8 | ダッシュボード | ✅ PASS |
| **test_pdf_simple.py** | 3 | PDF生成 | ✅ PASS |
| **test_email_template.py** | 8 | メールテンプレート | ✅ PASS |
| **test_integration.py** | 4 | 統合テスト | ✅ PASS |
| **test_audit_search.py** | 7 | 監査ログ検索 | ✅ PASS |
| **test_exceptions.py** | 17  状態 |
|---------|----------|------|--------|------|
| 001_initial.py | 001_initial | 初期スキーマ (Sprint1 MVP) | - | ✅ 適用済み |
| 002_pricing_billing.py | 002_pricing_billing | 単価・請求モデル追加 | - | ✅ 適用済み |
| 003_add_users.py | 003_add_users | ユーザー・権限管理 | 2026-01-27 | 適用済み |
| 004_add_expense_incentive.py | 004_add_expense_incentive | 経費・インセンティブ | 2026-01-27 | 適用済み |
| 005_expense_incentive_targets.py | 005_expense_incentive_targets | 経費・インセンティブ統合 | 2026-01-27 | 適用済み |
| ff166af0ba6d_add_performance_indexes.py | ff166af0ba6d | パフォーマンスインデックス追加 | 2026-01-27 | 適用済み |

**マイグレーション確認コマンド:**
```powershell
alembic current  # 現在のリビジョン確認
alembic upgrade head  # 最新まで適用
```

| ファイル | Revision | 目的 | 作成日 |
|---------|----------|------|--------|
| 001_initial.py | 001_initial | 初期スキーマ (Sprint1 MVP) | - |
| 002_pricing_billing.py | 002_pricing_billing | 単価・請求モデル追加 | - |
| **003_add_users.py** | 003_add_users | ユーザー・権限管理 | 2026-01-27 |
| **004_add_expense_incentive.py** | 004_add_expense_incentive | 経費・インセンティブ | 2026-01-27 |
| **005_expense_incentive_targets.py** | 005_expense_incentive_targets | 経費・インセンティブ統合 | 2026-01-27 |

---

## Kintone連携ファイル (kintone_app/)

| ファイル | 目的 | エンコーディング |
|---------|------|-----------------|
| actuals_sample_sjis.csv | 実績サンプル | Shift-JIS |
| assignments_sjis.csv | アサインマスタ | Shift-JIS |
| clients_sjis.csv | クライアントマスタ | Shift-JIS |
| price_outsource_sjis.csv | 外注単価マスタ | Shift-JIS |
| price_sales_sjis.csv | 売上単価マスタ | Shift-JIS |
| projects_sjis.csv | 案件マスタ | Shift-JIS |
| sample/案件サンプル_取込テンプレ.csv | 案件サンプル取込テンプレ | UTF-8 |
| shift_slots_sjis.csv | シフト枠マスタ | Shift-JIS |
| workers_utf8.csv | 稼働者マスタ | UTF-8 |

---

## 依存関係グラフ

### モデル依存
```
base.py
  ↓
enums.py
  ↓
master.py (Worker, Client, Site, User, IncentiveRule)
  ↓
transaction.py (Project, Actual, Invoice, Payout, Expense, Incentive)
```

### サービス依存
```
auth.py (権限チェック)
  ↓
time_calc.py → recalculation.py
price_resolver.py → recalculation.py
audit.py → recalculation.py, expense_service.py, incentive_service.py

expense_service.py → invoice_service.py（経費行の自動追加で統合済み）
incentive_service.py → invoice_service.py, payout_service.py（インセンティブ行の自動追加で統合済み）
```

### テスト依存
```
conftest.py (session fixture)
  ↓
test_*.py → src/models/* → src/services/*
```

---

## 重要な設計パターン

### 1. ミックスイン (base.py)
- **TimestampMixin**: created_at, updated_at自動管理
- **SoftDeleteMixin**: deleted_atでsoft delete

### 2. デコレータパターン (auth.py)
- **@require_permission**: 関数レベルのアクセス制御

### 3. サービス層パターン
- **XXXService**: ビジネスロジックをモデルから分離
- **依存性注入**: Session, User をコンストラクタで受け取る

### 4. データクラス 優先度 |
|---------|------|--------|
| src/api/main.py (修正) | 完全版APIエンドポイント実装 | 高 |
| src/services/kintone_service.py (実装) | Kintone API連携の完全実装 | 高 |
| src/services/scheduler.py (実装) | スケジューラージョブ実装 | 中 |
| tests/test_api.py | APIエンドポイントのテスト | 中 |
| docs/API_REFERENCE.md | API仕様書 | 低 |

---

## 動作確認済み構成（2026-01-27時点）

### 環境
- Python: 3.13.9
- データベース: SQLite (`vanzai.db`, 458KB)
- APIサーバー: Uvicorn + FastAPI (簡易版)
- テスト: pytest 126/126 PASS

### 投入済みデータ
| テーブル | 件数 |
|---------|------|
| clients | 2 |
| workers | 3 |
| roles | 3 |
| project_types | 2 |
| sites | 2 |
| projects | 1 |

### 稼働中のサービス
- ✅ APIサーバー: http://localhost:8000
- ✅ Swagger UI: http://localhost:8000/api/docs
- ✅ Kintone連携: 実装済み（DB→Kintone同期、実績取得、エラー書き戻し）
- ✅ スケジューラー: 実装済み（`SCHEDULER_ENABLED=true` で有効化）

---

## トラブルシューティング

### よくある問題と解決策

1. **ModuleNotFoundError: Cannot import 'engine' from 'src.models.base'**
   - **原因:** `engine` と `SessionLocal` は `src.api.deps` にある
   - **解決:** `from src.api.deps import engine, SessionLocal`

2. **AttributeError: 'CsvImportService' object has no attribute 'import_clients'**
   - **原因:** サービスは関数形式で実装されている
   - **解決:** `CsvImportService.import_csv()` を使用

3. **TypeError: 'billing_address' is an invalid keyword argument for Client**
   - **原因:** モデルフィールド名が実装と異なる
   - **解決:** モデル定義を確認（`address`, `contact_name`, `contact_email`）

4. **ImportError: cannot import name 'InvoiceService'**
   - **原因:** サービスはクラスではなく関数形式
   - **解決:** `from src.services import invoice_service` → `invoice_service.generate_invoice()`

---

## 参考リンク

- [DESIGN_SPEC_v0.3.md](spec/DESIGN_SPEC_v0.3.md) - 仕様の正本
- [AGENTS.md](../AGENTS.md) - AI Agent行動ルール
- [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - デプロイメント手順
- [DEPLOYMENT_COMPLETION_2026-01-27.md](DEPLOYMENT_COMPLETION_2026-01-27.md) - 構築完了レポート
- [RUNBOOK_MONTHLY.md](../RUNBOOK_MONTHLY.md) - 月次運用手順

---

**最終更新日**: 2026-01-27  
**管理者**: GitHub Copilot (AI Assistant)  
**バージョン**: v1.1 (デプロイメント完了版)ntone_integration.py | Kintone API連携 |
| src/api/ | FastAPI エンドポイント定義 |
| tests/test_integration.py | 統合テスト |

---

**更新日**: 2026-01-27  
**管理者**: AI Agent
