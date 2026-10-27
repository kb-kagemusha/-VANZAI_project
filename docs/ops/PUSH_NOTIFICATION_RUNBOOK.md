# プッシュ通知 Runbook

最終更新: 2026-04-04

## 目的
スタッフ向け Web Push 通知の設定手順、確認手順、障害切り分け、今回のミスを運用に残す。

## 版番号運用
- 小さい変更でも、ユーザーが触る変更をデプロイする場合は版番号を必ず更新する
- ルール:
  - メジャーアップデート: 1桁目を上げる
  - マイナーアップデート: 2桁目を上げる
  - バグフィックス/軽微修正: 3桁目を上げる
- 2026-04-04 時点の運用版: `0.6.7`

## 前提条件
- VPS の `.env` に以下が設定されていること
  - `VAPID_PRIVATE_KEY`
  - `VAPID_PUBLIC_KEY`
  - `VAPID_SUBJECT`
- nginx で以下が no-cache になっていること
  - `/index.html`
  - `/sw.js`
- フロントの版表示が更新後の値に変わっていること

## スタッフ側の設定手順
1. スタッフ用サイトへログインする
2. 個人設定を開く
3. `プッシュ通知` セクションで `通知をONにする` を押す
4. ブラウザの通知許可で `許可` を選ぶ
5. `通知を有効にしました！` が表示されることを確認する

## ブラウザ別の注意
### iPhone / iPad Safari
- Safari で開くだけでは Web Push は使えない
- `共有` → `ホーム画面に追加` して、追加したアイコンから開く必要がある
- その状態で `設定` → `通知` を許可する

### Android Chrome
- Chrome のサイト設定で `通知` を許可する
- 端末本体のアプリ通知でも Chrome 通知が無効になっていないことを確認する
- `Google Play 開発者サービス` 周辺の不整合で `subscribe()` が固まる場合がある

## サーバー側の確認手順
### 1. 公開鍵API
以下に `200 OK` が出ること

```bash
grep -R -n '/api/worker/push/vapid-public-key' /var/log/nginx/api-access.log /var/www/vanzai/logs/api.log
```

### 2. 購読登録API
以下に `POST /api/worker/push/subscribe` が出ること

```bash
grep -R -n '/api/worker/push/subscribe' /var/log/nginx/api-access.log /var/www/vanzai/logs/api.log
```

### 3. DB 登録確認

```bash
/var/www/vanzai/.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, '/var/www/vanzai')
from dotenv import load_dotenv
load_dotenv('/var/www/vanzai/.env')
from src.api.deps import SessionLocal
from src.models.master import PushSubscription

db = SessionLocal()
try:
    print('count=', db.query(PushSubscription).count())
    rows = db.query(PushSubscription).order_by(PushSubscription.created_at.desc()).limit(20).all()
    for row in rows:
        print(row.worker_id, row.endpoint[:90], row.created_at)
finally:
    db.close()
PY
```

## 2026-04-03 時点の実測と切り分け結果
- `GET /api/worker/push/vapid-public-key` までは到達していた
- `POST /api/worker/push/subscribe` は 0 件だった
- `push_subscriptions` テーブルの登録件数は 0 件だった
- つまり、サーバー送信以前にブラウザ側の購読作成で止まっていた

## 今回のミス
1. 版番号を小変更で上げていなかった
   - ユーザーから見ると、変更済みかどうか判別しづらかった

2. 通知許可と購読登録を同じ意味として扱っていた
   - `Notification.permission === granted` でも、サーバー購読登録が 0 件のケースがあった
   - UI 上は `通知は有効です` に見えるが、実際には配信先が無かった

3. 登録失敗をフロントで握り潰していた
   - `catch(() => {/* silent */})` で原因が見えず、再現しても無反応に見えた

4. `push/vapid-public-key` ログだけで進んでいると誤認しやすかった
   - 実際に見るべきは `POST /api/worker/push/subscribe` と `push_subscriptions` の件数だった

5. iOS と Android Chrome の前提差を初動で明文化していなかった
   - iOS はホーム画面追加が必要
   - Android Chrome は通知権限と端末通知設定の両方を見る必要がある

6. `pushManager.permissionState()` を前段確認に入れたのが悪手だった
   - Android Chrome 環境でここが返らず、画面が `プッシュ通知の登録を確認しています...` のまま止まるケースがあった
   - 前段の `permissionState()` は使わず、`getSubscription()` / `subscribe()` にタイムアウトを掛ける方が実運用で安定する

## 現在の対処
- 個人設定で `通知許可済みだが購読未完了` を表示する
- `もう一度登録する` ボタンで再登録できるようにする
- 登録処理中は工程ごとのメッセージを表示する
   - `ブラウザに通知許可を要求しています...`
   - `Service Worker を登録しています...`
   - `Service Worker の準備を待っています...`
   - `公開鍵を取得しています...`
   - `既存の購読状態を確認しています...`
   - `新しいプッシュ購読を作成しています...`
   - `サーバーに購読情報を登録しています...`
- 個人設定画面で固定文言を先に入れると工程表示を隠してしまうため、画面側では固定の待機文言を出さずフックの進捗表示をそのまま出す
- `Notification.requestPermission()` が `default` を返した場合も、画面に失敗理由を出す
- タイムアウト時にブラウザ/端末設定の確認文言を返す

## 今後の確認順序
1. 版番号が更新されているか
2. `/api/worker/push/vapid-public-key` が 200 か
3. `/api/worker/push/subscribe` が発火しているか
4. `push_subscriptions` に行が入っているか
5. 通知作成時に `send_push_to_workers` が対象 worker_id を拾っているか
6. `push send failed` ログがないか
