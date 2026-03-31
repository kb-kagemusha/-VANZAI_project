# プロジェクト残タスク統合管理 - 2026年2月4日

## 📌 2026年2月16日 更新（最新状態）

- このドキュメントは **2026-02-04時点のスナップショット**。当時の文脈を保持するため本文は一部残置。
- App174「見積書・請求書の発行」改修、App165 `via_destination` 移行、関連ドキュメント更新は完了済み。
- 現在の実装状態は [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) と [kintone/FRONT_DASHBOARD_SETUP.md](kintone/FRONT_DASHBOARD_SETUP.md) を正本として参照。
- 残作業は主に **外部手動作業（Kintone運用設定・権限/トークン管理）**。
- 本リポジトリ内で完結する**ドキュメント残タスクは完了**。以下の未実施項目は外部環境作業または将来拡張メモとして扱う。

## 🎯 今セッション完了タスク

### ✅ 案件カテゴリマスタ実装（完了）
- [x] マスタCSVに階層構造追加（件数は運用で増減）
- [x] front_dashboard.jsのハードコード削除
- [x] App164から動的読み込み機能実装
- [x] データ登録スクリプト作成
- [x] ドキュメント整備（3ファイル）

**詳細**: [COMPLETION_REPORT_CATEGORY_MASTER_2026-02-04.md](COMPLETION_REPORT_CATEGORY_MASTER_2026-02-04.md)

---

## 📌 2026年2月7日 更新（実行ログ）

### ✅ 自動実行済み
- `scripts/add_kintone_missing_fields.py` 実行 → 追加対象なし（既存済み）
- `scripts/migrate_introducers_to_suppliers.py` 実行 → DRY RUN対象0件
- `alembic upgrade head` 実行 → 最新まで適用
- `scripts/import_master_data.py` 実行 → 既存データ検出でスキップ
- API起動確認 → `uvicorn src.api.main:app --reload` で起動確認

### ⚠️ 依然として手動/外部作業が必要
- Kintone新規アプリ作成（invoices / payouts）とフィールド設定
- 追加APIトークンの作成・設定（equipment, tasks, project_documents, incentive_rules, system_settings など）

---

## 🔴 緊急（手動作業が必要）

### 1. Workers アプリにフィールド追加
**ステータス**: 完了

**更新メモ（2026-02-16）**:
- `introducer_supplier_id` の整備は完了。
- 現在は `via_destination`（`下請け` / `紹介` / `VANZAI直接`）運用へ移行済み。

**手順**: [NEXT_SESSION_INSTRUCTIONS.md](../NEXT_SESSION_INSTRUCTIONS.md#運用開始前の残タスク) 参照
1. Workers アプリに `introducer_supplier_id` フィールド追加
2. `python scripts/add_kintone_missing_fields.py` 実行（推奨）
3. または手動追加

**所要時間**: 2分  
**影響範囲**: 紹介者管理機能

---

## 🟡 重要（運用前に必要）

### 2. 紹介者データ移行
**ステータス**: 完了

**更新メモ（2026-02-16）**:
- `scripts/migrate_introducers_to_suppliers.py` は旧移行（introducer_supplier）として完了済み。
- 追加で `group -> via_destination` の移行も完了し、`group` 依存は廃止済み。

**手順**:
```powershell
python scripts/migrate_introducers_to_suppliers.py
```

**所要時間**: 5分  
**影響範囲**: 既存稼働者の紹介者情報

---

### 3. 環境設定確認

#### 4.1 データベース初期化
```powershell
alembic upgrade head
```

#### 4.2 マスタデータ投入
```powershell
python scripts/import_master_data.py workers
python scripts/import_master_data.py clients
python scripts/import_master_data.py sites
python scripts/import_master_data.py roles
python scripts/import_master_data.py project_types
```

#### 4.3 API起動確認
```powershell
uvicorn src.main:app --reload
# http://localhost:8000/api/docs を確認
```

**所要時間**: 10分  
**影響範囲**: システム全体

---

## 🟢 通常（機能拡張）

### 5. Kintone同期スクリプト完成
**ステータス**: 部分実装（suppliersのみ完了）

**外部/将来メモ**:
- 他15アプリの同期スクリプト実装
- トランザクションデータ取り込み手順確立

**優先度**: 中  
**所要時間**: 各アプリ2時間（合計30時間）

---

### 6. カテゴリマスタ機能拡張
**ステータス**: 基本実装完了

**将来改善メモ**:
- カテゴリの有効/無効フラグ追加
- カテゴリ階層の可視化UI
- カテゴリ使用状況の統計
- 4階層目（曾孫カテゴリ）への拡張

**優先度**: 低  
**所要時間**: 各機能5-10時間

---

### 7. 運用ドキュメント完成
**ステータス**: 完了（2026-02-16）

**残り**:
- [x] ユーザー向けマニュアル作成（[docs/ops/USER_MANUAL.md](ops/USER_MANUAL.md)）
- [x] FAQ作成（[docs/ops/FAQ.md](ops/FAQ.md)）
- [x] RUNBOOK の実運用確認（[docs/ops/RUNBOOK_VALIDATION_2026-02-16.md](ops/RUNBOOK_VALIDATION_2026-02-16.md)）

**優先度**: 中  
**所要時間**: 10時間

---

### 8. 本番環境準備
**ステータス**: 未着手

**外部作業メモ**:
- PostgreSQL移行
- SSL/TLS設定（Nginx）
- JWT秘密鍵の安全な管理
- バックアップ設定
- 監視・ログ設定
- ユーザー権限設定

**優先度**: 低（開発環境で十分動作中）  
**所要時間**: 20時間

---

## 📊 タスク統計

> 以下は 2026-02-04 時点の参考値。最新進捗は上部「2026年2月16日 更新（最新状態）」を参照。

| カテゴリ | 完了 | 残り | 進捗率 |
|---|---|---|---|
| **緊急（手動）** | 1 | 2 | 33% |
| **重要（運用前）** | 0 | 2 | 0% |
| **通常（機能拡張）** | 1 | 3 | 25% |
| **本番環境** | 0 | 1 | 0% |
| **合計** | 2 | 8 | 20% |

---

## 🎯 推奨アクション順序

### 今すぐ実行（10分）
1. **App164フィールド設定** → カテゴリ選択機能が使える
2. **Workers フィールド追加** → 紹介者管理の準備完了

### 次回セッション（30分）
3. **紹介者データ移行** → 既存データの移行完了
4. **環境設定確認** → API動作確認

### 運用開始後（随時）
5. **Kintone同期スクリプト** → 残りアプリの自動化
6. **運用ドキュメント** → ユーザー教育
7. **カテゴリ機能拡張** → UI改善
8. **本番環境準備** → スケールアップ

---

## 📁 関連ドキュメント

### 今セッション成果物
- [COMPLETION_REPORT_CATEGORY_MASTER_2026-02-04.md](COMPLETION_REPORT_CATEGORY_MASTER_2026-02-04.md) - カテゴリマスタ実装レポート
- [kintone/QUICK_START_APP164.md](kintone/QUICK_START_APP164.md) - 5分セットアップガイド
- [kintone/CATEGORY_MASTER_SETUP.md](kintone/CATEGORY_MASTER_SETUP.md) - 詳細技術ガイド
- [kintone/APP164_MANUAL_SETUP.md](kintone/APP164_MANUAL_SETUP.md) - 手動セットアップ手順

### 既存ドキュメント
- [NEXT_SESSION_INSTRUCTIONS.md](../NEXT_SESSION_INSTRUCTIONS.md) - 次セッション引き継ぎ
- [NEXT_SESSION_KINTONE.md](../NEXT_SESSION_KINTONE.md) - Kintone実装フェーズ
- [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - デプロイメントガイド
- [RUNBOOK_MONTHLY.md](../RUNBOOK_MONTHLY.md) - 月次運用手順
- [RUNBOOK_WEEKLY.md](../RUNBOOK_WEEKLY.md) - 週次運用手順

---

**最終更新**: 2026年2月16日  
**次のアクション**: 外部手動作業（Kintone運用設定・権限・本番基盤）を実施
