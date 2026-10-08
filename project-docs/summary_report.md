# summary_report.md

## 1. システム概要
VANZAIは、案件運用から請求・支払までを月次業務として再現可能に運用するための統合システムである。FastAPI + SQLAlchemy + React（admin-web / staff-mobile）を中核に、計算スナップショット、版管理、締め処理、監査ログを組み合わせて会計整合性を担保している。

## 2. 特徴的な設計
- スナップショット会計: actualに時間計算結果・適用単価を固定保存
- 非破壊訂正: invoice/payoutを版管理し、発行後上書きを避ける
- 締めガード: Soft/Hard closeと解除制約で改変境界を明確化
- 履歴駆動運用: payout_deliveries / audit_logsで送信・操作履歴を追跡
- 段階移行: 既存資産を活かし画面層を段階的に自前化

## 3. 再利用価値の高い部分
- period_key中心の月次運用モデル
- role/permissionの二段認可（UI補助 + API強制）
- DataTable + FilterBar + Paginationの一覧テンプレート
- ObjectStorage抽象による保存先差し替え設計
- reminder/escalationを含む通知運用モデル

## 4. 技術的負債
- ドキュメントの新旧情報が混在
- API経路に履歴由来の揺れが残る領域がある
- SQLite/PG差分によりmigration運用知識が必要
- main.py と main_simple.py の二重管理
- Kintone境界が部分的に残存

## 5. 他案件へ移植可能な機能
- CSV洗い替え + 重複防止フロー
- 月次請求/支払の明細正本設計
- 締め/解除 + 監査ログ一体モデル
- スタッフ向け予定返信・打刻・可否登録導線
- 支払送信履歴を軸にした再送運用UI

## 6. コード照合結果（2026-06-10）

- API 正本: `src/api/main.py`（100 EP）。締めは `/api/closing/*`、監査は `POST /api/audit/search`
- 仕様正本: `docs/spec/DESIGN_SPEC_v0.3.md`（復元たたき台）
- 実装ギャップ: `project-docs/CODE_VERIFIED_GAPS.md`（P0〜P3 優先度付き）
- 主な P0: 締め×取込/帳票未連携、請求時間軸不一致、reissue 明細欠落、aggregation 無認証

## 要確認
- 本番でのDB方針（PostgreSQL一本化か、開発時SQLite併用継続か）
- Kintoneの最終停止条件と運用切替手順
- 締めガード統合の実装スケジュール
