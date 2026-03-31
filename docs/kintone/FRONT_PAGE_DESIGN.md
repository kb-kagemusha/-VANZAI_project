# Kintone フロントページ設計書（テスト環境）

## 1. 目的
Kintoneゲストスペース内で、
「したいこと」から各アプリへワンクリックで遷移できるフロントページを提供する。

## 2. 適用範囲
- ゲストスペース運用（テスト環境）
- 既存Kintoneアプリ（案件・シフト・実績・請求・支払・経費・インセンティブ等）

## 3. 成果物
- 生成HTML（最小）: [docs/kintone/front_page.html](front_page.html)
- 生成JS（ポータル表示）: [kintone_app/customizations/front_portal.js](../../kintone_app/customizations/front_portal.js)
- CSS（ポータル表示）: [kintone_app/customizations/front_portal.css](../../kintone_app/customizations/front_portal.css)
- 生成スクリプト: [scripts/generate_kintone_front_page.py](../../scripts/generate_kintone_front_page.py)
- 登録ダッシュボード設定: [docs/kintone/FRONT_DASHBOARD_SETUP.md](FRONT_DASHBOARD_SETUP.md)

## 4. 配置先（フロントページURL）
### 4.1 ゲストスペースのURL
- https://{KINTONE_SUBDOMAIN}.cybozu.com/k/guest/{KINTONE_GUEST_SPACE_ID}/

### 4.2 フロントページの公開場所
- ゲストスペースの**ポータル**に [docs/kintone/front_page.html](front_page.html) の内容を貼り付けて公開
- ポータルの「JavaScript / CSSでカスタマイズ」に以下を追加
  - [kintone_app/customizations/front_portal.js](../../kintone_app/customizations/front_portal.js)
  - [kintone_app/customizations/front_portal.css](../../kintone_app/customizations/front_portal.css)
- 公開後、フロントページのURLは **ゲストスペースのトップURL** となる

## 5. データソース（.env）
フロントページのリンクは以下の環境変数から生成する。
- KINTONE_SUBDOMAIN
- KINTONE_GUEST_SPACE_ID
- KINTONE_APP_*（各アプリID）

追加で利用するキー（運用導線）
- KINTONE_APP_FRONT_DASHBOARD（登録ダッシュボード / App174）
- KINTONE_APP_PROJECT_ASSIGNMENTS（案件登録・確認の起点）
- KINTONE_APP_STAFF_MANAGERS（クライアント職員マスタ）

## 6. リンク仕様
- ゲストスペース有り:
  - https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/{app_id}/
- ゲストスペース無し:
  - https://{subdomain}.cybozu.com/k/{app_id}/

### 新規追加ページ
- ゲストスペース有り:
  - https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/{app_id}/edit
- ゲストスペース無し:
  - https://{subdomain}.cybozu.com/k/{app_id}/edit

## 7. 画面要件
- 「したいこと」をボタン（カード）として表示
- ボタン押下で該当アプリへ遷移
- 未設定のアプリIDは「未設定」表示（リンク無効）
- 主要アプリは「一覧を開く」「新規追加」の2ボタンを表示
- ヘッダーにスペースURLを明示（現在は非表示）
- 登録ダッシュボードへの導線を追加
- ポータル本文は最小HTML、UIはJSで生成

## 8. 生成手順
1. .env に以下を設定
  - KINTONE_SUBDOMAIN
  - KINTONE_GUEST_SPACE_ID
  - KINTONE_APP_*（該当アプリID）
2. 生成スクリプト実行
  - C:/VANZAI_project/.venv/Scripts/python.exe scripts/generate_kintone_front_page.py
3. 出力された [docs/kintone/front_page.html](front_page.html) をゲストスペースのポータルへ貼り付け
4. ポータルの「JavaScript / CSSでカスタマイズ」に以下を追加して保存
  - [kintone_app/customizations/front_portal.js](../../kintone_app/customizations/front_portal.js)
  - [kintone_app/customizations/front_portal.css](../../kintone_app/customizations/front_portal.css)

## 9. テスト観点
- フロントページから各ボタンをクリックし、該当アプリが開くこと
- GAIA_AP01（アプリ未検出）が出ないこと
- 未設定のアプリは「未設定」表示で遷移できないこと
- ポータル本文HTMLが10,000文字未満であること

## 10. セキュリティ
- フロントページにAPIトークン等の秘匿情報は含めない
- 公開範囲はゲストスペースの権限に準拠
