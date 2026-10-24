# 旧ファイル（現在は使用しない）

このフォルダのファイルは、過去の Kintone 連携・移行で使ったスクリプトです。**現在は使用していません。実行しないでください。**

本番と日常の開発は、管理画面（admin-web）・スタッフ画面（staff-mobile）・API（FastAPI）だけで完結します。Kintone API は呼びません。

## 置き場所

2026-10-11 に `scripts/` および `scripts/legacy/kintone/` から、プロジェクト直下の `.old/` へ移しました。

| 中身 | パス |
|------|------|
| 旧 Kintone サービス | `.old/kintone/`（`kintone_service.py` など） |
| 同期・フィールド更新・アプリ投入などの単発スクリプト | `.old/*.py` と `.old/*.ps1` |

`kintone_app/` と `docs/kintone/` は、当時の CSV と手順の記録として元の場所に残しています。こちらも現行運用の正本ではありません。

## 参照

- 起動やテストの現行コマンド: `QUICK_REFERENCE.md`
- 経緯: `docs/kintone/README.md`

古い手順書が `scripts/sync_db_to_kintone.py` のように書いている場合も、実体はこのフォルダにあります。パスを書き換えて動かす運用には戻しません。
