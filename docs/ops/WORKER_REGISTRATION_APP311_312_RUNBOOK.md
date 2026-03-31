# 稼働者登録運用（App311 / App312）Runbook

更新日: 2026-02-13

## 目的
- 個人稼働者: App312 で登録・承諾運用
- 法人（紹介者/下請け）: App311 で登録
- App165 は将来的に廃止予定

## 反映済み内容
1. App311 / App312 のフィールドコードを業務名に合わせて更新
2. App312 に CSV移行（`kintone_app/sample/VANZAI：稼働者データ（Googleフォーム連携）.csv`）
3. App174フロント（登録ダッシュボード）を App312 / App311 へ接続変更
4. App312 承諾時の有効化JSを追加（承諾時に経由先・紹介者/下請けを入力、稼働者ID自動採番）

## 追加/更新ファイル
- `scripts/update_app311_312_field_codes.py`
- `scripts/migrate_app312_from_csv.py`
- `kintone_app/customizations/app312_approval.js`
- `kintone_app/customizations/front_dashboard.js`（App174向け）

## 実行済みコマンド
```powershell
C:/VANZAI_project/.venv/Scripts/python.exe scripts/update_app311_312_field_codes.py
C:/VANZAI_project/.venv/Scripts/python.exe scripts/migrate_app312_from_csv.py
```

## 運用仕様（App312）
- 新規登録直後は `is_active=無効`
- 運営が「承諾」を実行するタイミングで:
  - 経由先を入力（必須）
  - 紹介者/下請けを入力（必須）
  - `worker_id` を `WRK` + 4桁で自動採番
  - `is_active` を `有効` に設定

## App312のJS適用手順
1. App312 を開く
2. 「アプリの設定」→「JavaScript / CSSでカスタマイズ」
3. `kintone_app/customizations/app312_approval.js` を追加
4. 保存して「アプリを更新」

## App174のJS適用手順
1. App174（front_dashboard）を開く
2. 「アプリの設定」→「JavaScript / CSSでカスタマイズ」
3. `kintone_app/customizations/front_dashboard.js` を再アップロード
4. 保存して「アプリを更新」

## 備考
- App312 の重複チェックは「承諾」時に氏名+フリガナ+電話で判定
- 採番は App312 内の最新 `WRKxxxx` を基準に次番号を割当
