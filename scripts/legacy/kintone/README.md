# Kintone レガシー資産（非推奨）

本番運用は **VPS（FastAPI + PostgreSQL + admin-web / staff-mobile）のみ** で完結する。
このディレクトリは過去の Kintone 移行・検証用スクリプト向けに残置している。

- `kintone_service.py` / `kintone_field_mappings.py` — 旧 `src/services/` から移動
- 関連スクリプト: `scripts/sync_db_to_kintone.py` 等（ルート `scripts/` 配下）

新規機能・本番デプロイでは Kintone API を呼ばないこと。
