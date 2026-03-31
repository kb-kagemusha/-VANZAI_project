# 次セッション引き継ぎ指示書（2026-02-16更新）

> 履歴注記（2026-02-16）
> 本書は引き継ぎ履歴として保持。最新の実装変更は `docs/IMPLEMENTATION_LOG.md`、画面運用は `docs/kintone/FRONT_DASHBOARD_SETUP.md`、ドキュメント運用は `docs/REMAINING_TASKS_2026-02-04.md` を正本参照。

## 🎯 プロジェクト概要
**VANZAI案件・シフト・実績・請求・支払 一元管理システム**
- スプレッドシート運用からの脱却
- 誰でも案件管理から請求書発行・支払明細作成まで再現可能に

---

## ✅ 前セッション完了事項（2026-01-30）

### 実装完了（25タスク）
1. **基礎実装完了**（15タスク）
   - 権限管理、単価スナップショット、請求書・支払明細
   - 再計算サービス、経費・インセンティブ管理
   - 集計サービス完全書き換え、PDF生成機能
   - ダッシュボード、統合テスト、ドキュメント整備

2. **統合・完成**（10タスク）
   - EmailSender/PDF/JWT/Manager統合
   - suppliersマスタ実装
   - Kintone連携（suppliersマスタ同期成功）
   - **Kintoneフィールド名日本語化完了（14アプリ）**

### テスト結果
```
126 passed in 4.93s（全件合格）
```

### Kintone連携状況
- **6マスタ同期可能**: workers, clients, sites, roles, project_types, suppliers
- **フィールド名日本語化**: 14アプリ×合計72フィールド完了
- **使用API**: プレビューAPI経由（`/v1/preview/app/form/fields.json`）

---

## 📋 運用開始前の残タスク（手動作業）

### 1. Kintone設定（1項目）
- [x] **Workers アプリに introducer_supplier_id フィールド追加**
  - フィールドコード: `introducer_supplier_id`
  - フィールド名: `紹介者（下請けID）`
   - 型: suppliers の `supplier_id` と同じ型（推奨: 文字列1行 or 数値）
  - 参照: [docs/kintone/SUPPLIERS_KINTONE_APP_SETUP.md](docs/kintone/SUPPLIERS_KINTONE_APP_SETUP.md)
   - 自動化（推奨）: `python scripts/add_kintone_missing_fields.py`

### 2. データ移行（1項目）
- [x] **紹介者データの移行実行**
  - スクリプト: `scripts/migrate_introducers_to_suppliers.py`
   - 内容: workers.introducer_worker_id（旧方式）→ suppliers 作成 + workers.introducer_supplier_id 更新
  - 実行前にバックアップ推奨
   - 実行手順: `--commit` なしは dry-run（安全）

### 3. 運用フロー確立（2項目）
- [x] **バンドル価格の手入力運用フロー確立**
  - 複数案件の一括請求時の価格設定方法を決定
  - 参照: [docs/spec/DRV_PAYOUT_RULES.md](docs/spec/DRV_PAYOUT_RULES.md)
  
- [x] **紹介者登録フロー（Kintone経由）**
  - 新規紹介者の登録手順をマニュアル化
  - 支払明細生成フロー（supplier_id ベース）の確立

---

## 📁 重要ファイルの場所

### 仕様・設計ドキュメント
- **正本**: [docs/spec/DESIGN_SPEC_v0.3.md](docs/spec/DESIGN_SPEC_v0.3.md)
- **決定ログ**: [docs/decisions/DECISION_LOG.md](docs/decisions/DECISION_LOG.md)
- **DRV案件ルール**: [docs/spec/DRV_PAYOUT_RULES.md](docs/spec/DRV_PAYOUT_RULES.md)

### 運用手順書
- **月次運用**: [RUNBOOK_MONTHLY.md](RUNBOOK_MONTHLY.md)
- **週次運用**: [RUNBOOK_WEEKLY.md](RUNBOOK_WEEKLY.md)
- **デプロイ手順**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

### Kintone関連
- **実装ガイド**: [docs/kintone/KINTONE_IMPLEMENTATION_GUIDE.md](docs/kintone/KINTONE_IMPLEMENTATION_GUIDE.md)
- **フィールド日本語化マニュアル**: [docs/kintone/FIELD_LABELS_JAPANESE_MANUAL.md](docs/kintone/FIELD_LABELS_JAPANESE_MANUAL.md)
- **suppliersマスタセットアップ**: [docs/kintone/SUPPLIERS_KINTONE_APP_SETUP.md](docs/kintone/SUPPLIERS_KINTONE_APP_SETUP.md)
- **フィールド日本語化ツール**: [tools/update_field_labels_jp.py](tools/update_field_labels_jp.py)
- **実行ログ**: [tools/update_field_labels_jp_log.txt](tools/update_field_labels_jp_log.txt)

### 完了報告
- **最終完了報告**: [docs/FINAL_COMPLETION_REPORT_2026-01-30.md](docs/FINAL_COMPLETION_REPORT_2026-01-30.md)
- **Task 24完了**: [docs/TASK_24_KINTONE_SYNC_COMPLETION.md](docs/TASK_24_KINTONE_SYNC_COMPLETION.md)
- **実装状況**: [docs/ops/STATUS.md](docs/ops/STATUS.md)

---

## 🛠️ 技術スタック

### 言語・フレームワーク
- Python 3.13.9
- SQLAlchemy 2.x（ORM）
- Alembic（マイグレーション）
- pytest（テスト: 126件全合格）
- FastAPI（API: 認証エンドポイント実装済み）

### データベース
- SQLite（開発環境）
- PostgreSQL対応可（環境変数で切替可能）

### 外部連携
- Kintone API（6マスタ同期、プレビューAPI経由で更新可能）
- SMTP（EmailSender統合済み）

### 主要サービス（14個）
1. CSV取り込み（洗い替え、二重化防止）
2. 時間計算（丸め、休憩、深夜割増）
3. 単価解決（優先順位、スナップショット）
4. 請求書生成（版管理、訂正/再発行）
5. 支払明細生成（版管理、訂正）
6. 紹介者支払明細生成（日額単価、人工単位）
7. 締め処理（Soft/Hard Close、解除ガード）
8. 集計（予定/確定の区別、CANCELED除外）
9. ダッシュボード（未処理項目、締め状況）
10. 監査ログ（全操作記録）
11. 再計算（プレビュー、Hard Closeガード）
12. PDF生成（請求書・支払明細）
13. EmailSender（SMTP統合、週次催促、月次承認依頼）
14. JWT認証（access/refresh token、bcrypt）

---

## ⚠️ 重要な注意事項

### 絶対ルール（AGENTS.md より）
1. **推測で仕様を埋めない**
   - 不明点は Issue 化ではなく、暫定案を提示して決定待ち
   
2. **既存データを破壊しない**
   - 物理削除、上書きをデフォルトで行わない
   - 金額と時間は必ず再現可能にする
   
3. **「締め解除」はガードレール込み**
   - 回数上限、二者承認、再締め期限、監査ログ
   
4. **フィールドコードは不変**
   - Kintoneフィールドコードは絶対に変更しない
   - CSV取込・バッチ処理に影響するため

### 監査ログ必須ポイント
- import_batch: 取込日時、ファイル名、成功/エラー/スキップ
- audit_log: 単価変更、再計算、請求発行/再発行、支払確定、締め/解除
- invoice/payout: version、親子関係、PDF参照

### 破綻防止ガード
- CSV再取り込み: 二重化しない（洗い替えモード）
- canceled assignment: actualを集計対象から除外
- 丸め/休憩/端数: ルールをマスタ化、適用結果を保存

---

## 🚀 次のアクションプラン

### 優先度1: 運用開始準備（手動作業）
1. Workers アプリへのフィールド追加
2. データ移行実行
3. 運用フロー確立

### 優先度2: 本番デプロイ準備
- （外部）環境変数の本番設定確認
- （外部）データベース選定（SQLite or PostgreSQL）
- （外部）SMTP設定（Gmail/SendGrid/AWS SES）
- （外部）スケジューラー起動確認

### 優先度3: ドキュメント最終確認
- [x] RUNBOOK の動作確認（[docs/ops/RUNBOOK_VALIDATION_2026-02-16.md](docs/ops/RUNBOOK_VALIDATION_2026-02-16.md)）
- [x] ユーザー向けマニュアル作成（[docs/ops/USER_MANUAL.md](docs/ops/USER_MANUAL.md)）
- [x] FAQ作成（[docs/ops/FAQ.md](docs/ops/FAQ.md)）

---

## 📞 トラブルシューティング

### Kintone関連
- **フィールド名変更**: プレビューAPI経由で変更（`tools/update_field_labels_jp.py`）
- **フィールドコード変更**: **絶対禁止**（データ連携が壊れる）
- **同期エラー**: `scripts/sync_db_to_kintone.py` のログ確認

### テスト実行
```bash
pytest tests/ -q --tb=short
```

### データベース初期化
```bash
alembic upgrade head
```

### Kintone同期
```bash
python scripts/sync_db_to_kintone.py [マスタ名]
# 例: python scripts/sync_db_to_kintone.py suppliers
```

---

## 📊 現在の統計

| 項目 | 数値 |
|:----|:-----|
| 完了タスク | 25/25 (100%) |
| テスト | 126/126 passed |
| コード品質 | TODO 0件、エラー 0件 |
| Kintone連携 | 6マスタ同期可能 |
| フィールド日本語化 | 14アプリ×72フィールド完了 |
| ドキュメント | 16ファイル完備 |
| 実装サービス | 14サービス |

---

## 🎯 プロジェクトゴール

### 達成済み
- ✅ 25タスク完全制覇
- ✅ 126テスト全件合格
- ✅ Kintone連携完了（6マスタ）
- ✅ フィールド名日本語化完了（14アプリ）
- ✅ 実装ドキュメント完備

### 残タスク
- 外部手動作業（Kintone運用設定）
- 本番デプロイ準備

---

## 📝 セッション終了時メモ（2026-01-30 02:15）

### 最後の作業
- Kintoneフィールド名日本語化をプレビューAPI経由で完了
- 14アプリ、合計72フィールドを日本語化
- 全アプリデプロイ成功（SUCCESS）

### 環境変数（.env）
- `KINTONE_ADMIN_USER`: kagemusha_api_user
- `KINTONE_ADMIN_PASSWORD`: 設定済み（作業完了後は削除推奨）

### 次の注意点
- .env の管理者パスワードは作業完了後に削除すること
- 運用開始前の手動作業（4項目）を実施すること
- データ移行前にバックアップを取ること

---

## 🔗 参考リンク

- プロジェクトルート: `C:\VANZAI_project`
- GitHub: （リポジトリURLがあればここに記載）
- Kintone: https://xtf5wpxp3gk2.cybozu.com/k/guest/3/
- ドキュメント: [docs/](docs/)

---

**作成日**: 2026-01-30  
**作成者**: AI Agent (Copilot)  
**ステータス**: 実装タスク全完了、運用開始準備待ち  
**次のセッション**: 運用開始準備（手動作業）の実施

### 【オプション】ステップ6: 本番環境準備
- PostgreSQL移行
- Systemdサービス化（Linux）
- Nginx設定
- 認証・認可（JWT/OAuth2）

---

## 📋 実装時の重要ルール（AGENTS.mdより）

### 絶対ルール
1. **推測で仕様を埋めない** → 不明点は暫定案を提示して決定待ち
2. **既存データを破壊しない** → 物理削除・上書きは慎重に
3. **金額と時間は再現可能に** → スナップショット、監査ログ必須
4. **締め後の計算結果が変わらない** → テストで保証

### 実装の進め方
1. まず `DESIGN_SPEC_v0.3.md` を読む（セクション単位で参照）
2. DB変更が必要ならマイグレーション作成
3. 監査ログを出力する
4. テストを追加する
5. 1PR=1テーマで進める

### コミットメッセージ
```
feat: Kintone実績取得の実装

- get_actuals() でAPIから実績を取得
- 日付範囲フィルタリング対応
- エラーハンドリング追加

参照: DESIGN_SPEC_v0.3 セクション6
```

---

## 🎯 最初の指示例（コピー&ペースト用）

```
以下の手順で実装を進めてください：

1. `.env` ファイルを作成
   - `.env.example` をコピー
   - `kintone_app/アプリ一覧 (VANZAI).csv` からKintoneアプリIDを取得して設定
   - SMTP設定はGmail（開発用）で設定

2. DB初期化
   - `alembic upgrade head` 実行
   - テーブル作成の確認

3. 初期データ投入
   - `scripts/import_master_data.py` を実行
   - エラーがあれば修正

4. API起動して動作確認
   - `uvicorn src.api.main:app --reload`
   - Swagger UIで動作確認

実装中は以下を遵守：
- AGENTS.mdのルールを守る
- 不明点は暫定案を提示
- 監査ログを必ず出力
- テストで動作保証

途中で問題があれば報告してください。
```

---

## 📚 参照ドキュメント（重要度順）

1. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - 実装の8ステップ詳細
2. **[AGENTS.md](AGENTS.md)** - AI agentの行動ルール
3. **[docs/spec/DESIGN_SPEC_v0.3.md](docs/spec/DESIGN_SPEC_v0.3.md)** - 仕様の正本
4. **[.env.example](.env.example)** - 環境変数テンプレート
5. **[docs/TASK_COMPLETION_2026-01-27.md](docs/TASK_COMPLETION_2026-01-27.md)** - 完了済みタスク
6. **[RUNBOOK_MONTHLY.md](RUNBOOK_MONTHLY.md)** - 月次運用手順
7. **[docs/decisions/DECISION_LOG.md](docs/decisions/DECISION_LOG.md)** - 意思決定ログ

---

## 🚨 トラブルシューティング

### よくある問題
1. **ModuleNotFoundError**: `pip install -e .` を実行
2. **alembic エラー**: `rm vanzai.db` してから `alembic upgrade head`
3. **SMTP認証エラー**: Gmailアプリパスワードを使用
4. **Kintone接続エラー**: サブドメインとAPIトークンを確認

### 確認コマンド
```powershell
# Python環境確認
python --version  # 3.13.9

# パッケージ確認
pip list | Select-String "fastapi|sqlalchemy|alembic"

# DB確認
python -c "from src.models.base import engine; print(engine.table_names())"

# テスト実行
pytest -v
```

---

## ✅ 完了条件

### ステップ1-3完了時
- （テンプレート）`.env` ファイル作成済み
- （テンプレート）`alembic upgrade head` 成功
- （テンプレート）`vanzai.db` ファイル存在
- （テンプレート）マスタデータ投入成功（最低限: clients, workers, roles）
- （テンプレート）API起動成功（http://localhost:8000/api/docs アクセス可能）
- （テンプレート）`GET /api/health` が200 OKを返す

### 全ステップ完了時
- （テンプレート）Kintone連携実装済み（実績取得・エラー書き戻し）
- （テンプレート）スケジューラー実装済み（週次催促・月次請求書）
- （テンプレート）実際のCSVで実績取り込みテスト成功
- （テンプレート）請求書PDF生成テスト成功
- （テンプレート）銀行振込ファイル生成テスト成功
- （テンプレート）運用ドキュメント（RUNBOOK）で月次処理が回せる

---

**作成日**: 2026-01-27  
**対象セッション**: 実装・デプロイフェーズ  
**前提**: コード完成、テスト100%成功、ドキュメント完備
