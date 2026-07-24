# VANZAI Project - 案件・シフト・実績・請求・支払 一元管理システム

## 🆕 フロント運用メニュー状況（2026-02-18 06:48:20）

### 1. マスタ登録
- クライアント情報の登録
- クライアント職員（責任者・担当者）の登録
- VANZAI職員の登録
- 下請け（紹介者）の登録
- 案件種別の登録
- 現場情報の登録
- 稼働者情報の登録

### 2. 案件準備・運用
- 案件マスタの登録/確認
- 案件登録（カテゴリ分け、担当者設定）
- 実績管理（CSV取り込み・実績確認）

### 3. 請求・支払（経理業務）
- 見積書/請求書の発行・確認
- 支払明細書の発行・確認

### 4. 現在は準備中（表示はあるが未設定）
- 単価管理（売上単価・外注単価・単価ルール）
- シフト管理（枠/アサイン）
- 経費精算
- インセンティブ管理
- 支払明細送信
- 銀行振込（全銀データ）
- タスク進捗
- 案件資料
- 貸出備品/貸出履歴

## 🆕 最新アップデート (2026年2月16日)

- App174（見積書・請求書発行）改善、App171再構成、必要アプリの日本語ラベル統一（フィールドコード維持）を反映（詳細: [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md), [docs/kintone/FRONT_DASHBOARD_SETUP.md](docs/kintone/FRONT_DASHBOARD_SETUP.md)）

## 🆕 最新アップデート (2026年2月4日)

### ✅ 案件カテゴリマスタ実装完了
**機能**: フロントページの案件登録で大カテゴリ→中カテゴリ→小カテゴリの動的カスケード選択が可能に

**実装内容**:
- 49件のカテゴリデータをマスタで管理（App164）
  - 大カテゴリ: 4件
  - 中カテゴリ: 11件
  - 小カテゴリ: 34件
- ハードコード削除（157行 → 0行）
- マスタから動的読み込み（95行の新規実装）
- カスケード選択の自動絞り込み

**セットアップ**: [docs/kintone/QUICK_START_APP164.md](docs/kintone/QUICK_START_APP164.md)（5分で完了）  
**詳細レポート**: [docs/COMPLETION_REPORT_CATEGORY_MASTER_2026-02-04.md](docs/COMPLETION_REPORT_CATEGORY_MASTER_2026-02-04.md)

---

## 📋 概要

スプレッドシート運用で発生している**属人化と事務コスト**を解消し、誰でも案件管理から請求書発行・支払明細作成までを**再現可能**に回せる状態を作るシステムです。

### 主な機能
- ✅ **CSV取り込み**: 洗い替えモード、二重化防止、エラー差戻し
- ✅ **時間計算**: 丸め、休憩、深夜割増の自動計算
- ✅ **単価スナップショット**: 実績確定時に単価を保存し、後から変更されても再計算されない
- ✅ **請求書・支払明細**: 版管理、訂正、再発行に対応
- ✅ **締め処理**: Soft Close（解除可能）と Hard Close（二者承認必要）のガードレール
- ✅ **監査ログ**: すべての変更を記録し、追跡可能
- ✅ **権限管理**: ロールベースアクセス制御（admin/ops/accounting/site_manager/worker）
- ✅ **経費・インセンティブ**: 承認フロー、請求書・支払明細への自動反映
- ✅ **REST API**: FastAPIによる完全なREST API（Swagger UI対応）
- ✅ **メール送信**: SMTP統合（Gmail/SendGrid/AWS SES対応）
- ✅ **銀行振込**: 全銀フォーマット自動生成
- ✅ **Web管理画面**: admin-web（https://vanzai-portal.com）でマスタ・案件・請求・支払を一元管理
- ✅ **スケジューラー**: 週次催促・日次更新・月次請求書の自動実行

### 📊 実装状況
**テスト成功率**: 126/126 (100%)  
**Python**: 3.13.9  
**環境**: 開発環境構築完了（2026-01-27）  
**APIサーバー**: 起動確認済み (http://localhost:8000)

詳細は [docs/ops/STATUS.md](docs/ops/STATUS.md) を参照

設計書（[docs/spec/DESIGN_SPEC_v0.3.md](docs/spec/DESIGN_SPEC_v0.3.md)）から読み取れる「実装までのステップ」は [docs/ops/IMPLEMENTATION_STEPS_FROM_SPEC.md](docs/ops/IMPLEMENTATION_STEPS_FROM_SPEC.md) に整理しています。

**最新の実装 (Sprint 4 - 2026-01-27)**:
- ✅ 経費・インセンティブ統合（請求書・支払明細への自動反映）
- ✅ PDF生成機能（請求書・支払明細のPDF出力）
- ✅ メールテンプレート（7種類の通知テンプレート）
- ✅ ダッシュボード詳細バリデーション
- ✅ 統合テスト拡張（エラー復旧・並行処理）
- ✅ **開発環境構築完了**（`.env`、DB初期化、マスタデータ投入、API起動）

---

## 🏗️ アーキテクチャ

### 技術スタック
- **Python** 3.13.5
- **SQLAlchemy** 2.0.46 (ORM)
- **Alembic** 1.18.1 (マイグレーション)
- **pytest** 9.0.2 (テスト)
- **SQLite** (開発環境)

### ディレクトリ構成
```
VANZAI_project/
├── src/
│   ├── models/           # データモデル (master.py, transaction.py, enums.py)
│   └── services/         # ビジネスロジック
│       ├── csv_import.py        # CSV取り込み
│       ├── time_calc.py         # 時間計算
│       ├── price_resolver.py    # 単価解決
│       ├── invoice_service.py   # 請求書生成
│       ├── payout_service.py    # 支払明細生成
│       ├── aggregation.py       # 集計
│       ├── closing.py           # 締め処理
│       ├── dashboard.py         # ダッシュボード
│       ├── audit.py             # 監査ログ
│       ├── auth.py              # 権限管理
│       ├── recalculation.py     # 再計算
│       ├── expense_service.py   # 経費精算
│       ├── incentive_service.py # インセンティブ管理
│       ├── pdf_generator.py     # PDF生成
│       └── email_template.py    # メールテンプレート
├── tests/                # テストコード (126 tests passing)
├── alembic/              # DBマイグレーション
├── docs/                 # 仕様書・決定ログ
│   ├── spec/
│   │   ├── DESIGN_SPEC_v0.3.md
│   │   └── REVIEW_MERGE_v0.3.md
│   └── decisions/
│       └── DECISION_LOG.md
├── RUNBOOK_MONTHLY.md    # 月次運用手順書
├── RUNBOOK_WEEKLY.md     # 週次運用手順書
└── EMAIL_TEMPLATES.md    # メールテンプレート
```

---

## 🚀 クイックスタート（開発環境）

### 前提条件
- Python 3.13.9
- Git

### 手順

#### 1. 環境構築
```powershell
# リポジトリクローン
git clone <repository-url>
cd VANZAI_project

# 仮想環境作成・有効化
python -m venv .venv
.venv\Scripts\Activate.ps1

# 依存関係インストール
pip install -e .
```

#### 2. 環境変数設定
```powershell
# .env ファイルを作成（.env.example をコピー）
copy .env.example .env

# .env ファイルを編集
# - JWT_SECRET_KEY（本番は openssl rand -hex 32 で生成）
# - SMTP設定（開発環境はGmail推奨）
# - DATABASE_URL
```

#### 2.1 マスタデータ投入（CSV / 管理画面）

マスタは **admin-web** または CSV 取込で管理する（Kintone 連携は廃止）。

```powershell
# 例: テスト用マスタを投入
python scripts/import_master_data.py
```

本番運用は https://vanzai-portal.com のマスタ画面から登録・編集する。

#### 3. データベース初期化
```powershell
# マイグレーション実行
alembic upgrade head

# マスタデータ投入
python scripts/import_master_data.py
```

#### 4. APIサーバー起動
```powershell
# 開発サーバー起動
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Swagger UIで確認
# http://localhost:8000/api/docs
```

#### 5. 動作確認
```powershell
# テスト実行
pytest -v

# ヘルスチェック
curl http://localhost:8000/api/health
```

**所要時間**: 約5〜10分

---

## 🚀 セットアップ（詳細）

### 1. 環境構築
```bash
# Python 3.13+ が必要
python --version  # Python 3.13.5 推奨

# 仮想環境作成
python -m venv .venv

# 仮想環境有効化
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 依存関係インストール
pip install -e .
```

### 2. データベース初期化
```bash
# マイグレーション実行
alembic upgrade head

# 確認
alembic current
# 出力: ff166af0ba6d (head)

# マスタデータ投入（テスト用）
python scripts/import_master_data.py
# クライアント: 2件、稼働者: 3件、ロール: 3件 など
```

---

## ✅ 次のステップ・チェックリスト（実装/運用）

### A. 仕様の未決事項を確定
- [ ] 未決事項（銀行フォーマット/インセンティブ条件/Wヘッダーなど）を確定
- [ ] 決定内容を [docs/decisions/DECISION_LOG.md](docs/decisions/DECISION_LOG.md) に「理由付き」で記録

### B. 環境変数の本番想定セット
- [ ] `.env` に `JWT_SECRET_KEY` / `DATABASE_URL` を設定
- [ ] メール送信設定を有効化（初回は `EMAIL_DRY_RUN=true` 推奨）
- [ ] スケジューラーを使う場合は `SCHEDULER_ENABLED=true` を設定

### C. 管理画面の準備
- [ ] admin-web（https://vanzai-portal.com）にログインできることを確認
- [ ] マスタ（クライアント・稼働者・案件種別等）が登録済みであること

### D. 運用リハーサル（ローカル or 本番）
- [ ] 実績CSV取り込み → 集計 → 締め → 請求/支払生成 を通しで実行
- [ ] PDF生成（請求書/支払明細）を確認
- [ ] メール送信（dry-run）で文面を確認
- [ ] 全銀フォーマットの出力を確認

### E. デプロイ準備
- [ ] API起動コマンドを `uvicorn src.api.main:app ...` に統一
- [ ] Reverse Proxy/永続プロセス/ログ出力先を確定
- [ ] 運用RUNBOOKの差分を反映

### G. 追加実装（必要なものだけ）
- [ ] CSV取り込みのチャンク処理（Phase 2）
- [ ] Wヘッダーbundle単価の設計/実装（低優先度）
- [ ] JWT/OAuth2 認証導入
- [ ] フロントエンド実装

### 3. テスト実行
```bash
# 全テスト実行（126個）
pytest -v

# 出力:
# 126 passed in 2.42s

# 特定のテストのみ
pytest tests/test_csv_import.py -v

# カバレッジ付き
pytest --cov=src --cov-report=html
```

### 4. トラブルシューティング

#### ImportError: No module named 'src'
```bash
# 開発モードでインストール
pip install -e .
```

#### テスト失敗: Database locked
```bash
# SQLite WALモード無効化
rm -f vanzai.db-wal vanzai.db-shm
pytest -v
```

#### Alembicエラー: revision not found
```bash
# マイグレーション再実行
alembic downgrade base
alembic upgrade head
```

---

## 📖 使い方

### CSV取り込み
```python
from src.services.csv_import import CSVImportService, ImportMode, ImportScopeType
from decimal import Decimal

service = CSVImportService(session)

result = service.import_csv(
    file_content=csv_content,
    file_name="project_A_202601.csv",
    project_id="PROJECT_A_ID",
    period_key="202601",
    mode=ImportMode.REPLACE_SCOPE,  # 洗い替えモード
    scope_type=ImportScopeType.PROJECT_MONTH,
    default_price_sales=Decimal("1500"),
    default_price_outsource=Decimal("1200"),
)

# エラー確認
if result.errors:
    for err in result.errors:
        print(f"行{err.row_number}: {err.message}")
```

### 請求書生成
```python
from src.services.invoice_service import generate_invoice
from datetime import date

invoice = generate_invoice(
    session=session,
    client_id="CLIENT_A_ID",
    project_id="PROJECT_A_ID",
    period_key="202601",
    billing_date=date(2026, 2, 1),
    user_id="ops_user",
)

print(f"請求書ID: {invoice.id}, 金額: {invoice.total_amount}円")
```

### 締め処理
```python
from src.services.closing import soft_close, hard_close

# Soft Close（解除可能）
soft_close(
    session=session,
    project_id="PROJECT_A_ID",
    month_key="202601",
    user_id="admin_user",
)

# Hard Close（二者承認必要）
hard_close(
    session=session,
    project_id="PROJECT_A_ID",
    month_key="202601",
    user_id="admin_user",
    reason="月次確定",
)
```

---

## 🔐 権限管理

### ロール定義（仕様5章）
| ロール | 権限 |
|---|---|
| **Admin** | 全操作可能、締め解除の最終承認 |
| **Ops** | CSV取込、請求書生成、支払明細生成 |
| **Accounting** | 請求レビュー、支払承認 |
| **SiteManager** | CSV提出、実績確認 |

---

## 📊 テスト状況

### 現在のカバレッジ
```
✅ 99/99 tests passing (2026-01-28更新)
- test_audit_search.py: 7 tests
- test_auth.py: 13 tests
- test_closing.py: 7 tests
- test_csv_import.py: 6 tests
- test_dashboard.py: 5 tests
- test_exceptions.py: 17 tests ⭐NEW
- test_expense.py: 4 tests
- test_incentive.py: 4 tests
- test_integration.py: 2 tests
- test_invoice_payout.py: 4 tests
- test_price_resolver.py: 8 tests ⭐NEW
- test_recalculation.py: 6 tests
- test_time_calc.py: 16 tests
```

### テスト対象
- **CSV取り込み**: 二重化防止、洗い替え、エラー処理
- **時間計算**: 丸め、休憩自動計算、深夜割増
- **締め処理**: Soft/Hard Close、解除ガードレール
- **単価スナップショット**: applied_price_sales/outsource の保存
- **カスタム例外**: 11種類のドメイン例外の動作検証
- **単価解決**: 優先順位、有効期間境界値、外注単価

---

## 📝 運用ドキュメント

### 必読
1. **[DESIGN_SPEC_v0.3.md](docs/spec/DESIGN_SPEC_v0.3.md)** - システム仕様書（正本）
2. **[RUNBOOK_MONTHLY.md](RUNBOOK_MONTHLY.md)** - 月次運用手順
3. **[AGENTS.md](AGENTS.md)** - AI Agent向けルール

### 決定ログ
- [DECISION_LOG.md](docs/decisions/DECISION_LOG.md)
  - DEC-001: import_batch重複検知キー
  - DEC-002: period_key形式（YYYYMM）
  - DEC-003: アサインなし実績はエラー扱い

---

## 🔧 トラブルシューティング

### Q: CSV取込でエラーが大量発生
A: 
1. ファイルエンコーディングを確認（UTF-8必須）
2. 必須カラムの欠損を確認
3. `worker_id`, `role_id` がマスタに存在するか確認

### Q: 請求書金額が前月と大きく異なる
A:
1. 差分アラートを確認（`get_variance_alerts()`）
2. 単価マスタの変更履歴を確認
3. 実績件数を前月と比較

### Q: 締め後に誤りを発見
A:
1. 締め解除申請（二者承認が必要）
2. 解除理由と再締め期限を記録
3. 修正後、速やかに再締め

---

## 🛡️ 破綻を防ぐ必須ガード

### 1. CSV再取り込みの二重化防止
- 洗い替えモード: 同日×案件×稼働者を無効化してから投入
- file_hash による重複検知

### 2. 締め後の改変防止
- Hard Close後は再計算不可
- 解除には二者承認が必要
- 解除回数上限あり（デフォルト3回）

### 3. canceled assignment の除外
- Actual.status=INVALID に設定
- 集計から自動除外

---

## 📅 リリース履歴

### Sprint 4 (完了 - 2026-01-27)
- ✅ 経費・インセンティブ統合
- ✅ PDF生成機能（請求書・支払明細）
- ✅ メールテンプレート（7種類）
- ✅ ダッシュボード詳細バリデーション
- ✅ 統合テスト拡張
- ✅ **開発環境構築完了**（`.env`、DB初期化、マスタデータ、API起動）

### Sprint 3 (完了)
- ✅ 単価スナップショット統合
- ✅ RUNBOOK詳細化
- ✅ 請求書・支払明細テスト
- ✅ 再計算サービス
- ✅ ダッシュボードテスト

### Sprint 2 (完了)
- ✅ 単価マスタ（PriceSales/Outsource/Rule）
- ✅ 請求書・支払明細モデル
- ✅ 締め処理（Soft/Hard Close）
- ✅ 監査ログ

### Sprint 1 (完了)
- ✅ データモデル構築
- ✅ CSV取り込み（洗い替えモード）
- ✅ 時間計算サービス

### 現状（2026-01-30）
- ✅ 完全版API: `src/api/main.py`（Dashboard/請求/支払/締め 等）
- ✅ Web管理画面: admin-web / staff-mobile（VPS 上で運用）
- ✅ スケジューラー: env駆動（`SCHEDULER_ENABLED=true` で有効化）

### 運用拡張（任意）
- 本番DB（PostgreSQL）への移行
- 認証/権限の本番運用設計（ユーザー管理、鍵管理、監査）
- デプロイ（SSL/TLS、監視、バックアップ）

---

## 🤝 貢献

### 開発ルール
- すべての変更は `docs/spec/DESIGN_SPEC_v0.3.md` を正本とする
- 仕様変更は `docs/decisions/DECISION_LOG.md` に理由付きで記録
- コミット前に全テストPASS必須 (`pytest -v`)
- 破壊的変更は止まって質問

### コミット粒度
- 1 PR = 1 テーマ
- PRには以下を記載:
  - 仕様の参照箇所（セクション番号）
  - 追加したテスト
  - 監査ログの出力点

---

## 📞 サポート

- 仕様に関する質問: `docs/spec/DESIGN_SPEC_v0.3.md` を参照
- 運用に関する質問: `RUNBOOK_MONTHLY.md` を参照
- 技術的な質問: `AGENTS.md` を参照

## 📚 ドキュメント一覧

### 開発ガイド
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - デプロイメント8ステップ詳細手順
- **[NEXT_SESSION_INSTRUCTIONS.md](NEXT_SESSION_INSTRUCTIONS.md)** - 次セッション用AI Agent指示
- [AGENTS.md](AGENTS.md) - AI Agent行動ルール

### 仕様書
- [DESIGN_SPEC_v0.3.md](docs/spec/DESIGN_SPEC_v0.3.md) - 詳細設計仕様（正本）
- [REVIEW_MERGE_v0.3.md](docs/spec/REVIEW_MERGE_v0.3.md) - レビュー反映記録
- [DECISION_LOG.md](docs/decisions/DECISION_LOG.md) - 設計決定ログ

### 運用ガイド
- [STATUS.md](docs/ops/STATUS.md) - 実装状況と既知の制約
- [CSV_IMPORT_GUIDE.md](docs/ops/CSV_IMPORT_GUIDE.md) - CSV取り込み詳細手順
- [USER_MANUAL.md](docs/ops/USER_MANUAL.md) - ユーザー向け運用マニュアル
- [FAQ.md](docs/ops/FAQ.md) - 運用FAQ
- [RUNBOOK_MONTHLY.md](RUNBOOK_MONTHLY.md) - 月次運用手順
- [RUNBOOK_WEEKLY.md](RUNBOOK_WEEKLY.md) - 週次運用手順

### 完了レポート
- **[DEPLOYMENT_COMPLETION_2026-01-27.md](docs/DEPLOYMENT_COMPLETION_2026-01-27.md)** - デプロイメント完了レポート
- [COMPLETION_REPORT.md](docs/COMPLETION_REPORT.md) - 実装完了レポート（タスクA〜H）
- [TASK_COMPLETION_2026-01-27.md](docs/TASK_COMPLETION_2026-01-27.md) - 全8タスク完了レポート

### リファレンス
- [FILE_INDEX.md](docs/FILE_INDEX.md) - 全ファイルの役割と依存関係
- [EMAIL_TEMPLATES.md](EMAIL_TEMPLATES.md) - メールテンプレート仕様

### API仕様
主要サービス一覧は [src/services/](src/services/) 配下を参照

---

## ライセンス

MIT License

---

**Last Updated**: 2026-02-16
