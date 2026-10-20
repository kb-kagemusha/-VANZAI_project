# Kintone 関連ドキュメント（アーカイブ）

> **ステータス（2026-07-24）**: 本番運用から Kintone 連携は**完全に除去**済みです。  
> 本番の正本は **PostgreSQL + admin-web / staff-mobile + FastAPI API** のみです。

## このディレクトリの位置づけ

- 過去の Kintone 移行期（〜2026年7月）のセットアップ手順・フィールド定義メモ
- **新規開発・本番デプロイでは参照しない**（履歴・移行調査用）

## レガシーコードの所在

旧 Kintone 用スクリプトは **現在未使用** です。本番・ローカル開発とも実行しません。

| 種別 | パス |
|------|------|
| 旧スクリプト一式 | `.old/`（2026-10-11 に `scripts/` から移動） |
| Python サービス（旧） | `.old/kintone/`（旧 `scripts/legacy/kintone/`） |
| CSV・カスタマイズ資産 | `kintone_app/`（過去の書き出し。現行取込の正本ではない） |

このフォルダ内の古い手順が `scripts/sync_db_to_kintone.py` などを指していても、実体は `.old/` にあります。パスを直して実行しないでください。

## 現行運用ドキュメント

- クライアント向け機能一覧: [docs/CLIENT_FEATURE_SUMMARY.md](../CLIENT_FEATURE_SUMMARY.md)
- 運用マニュアル: [docs/ops/USER_MANUAL.md](../ops/USER_MANUAL.md)
- FAQ: [docs/ops/FAQ.md](../ops/FAQ.md)

## 変更履歴

- Ver.0.11.36〜0.11.37（2026-07-24）: 本番コードから Kintone 依存を除去。詳細はルート `CHANGELOG.md` を参照。
