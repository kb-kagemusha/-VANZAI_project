# OCR 外部アップロード — 運用 Runbook

Ver.0.11.0 以降。正本コード: `src/services/ocr_upload_link_service.py`, `src/api/public_ocr_routes.py`

---

## 1. 初回セットアップ（本番 VPS）

### 1-1. `.env` にシークレット追加

```bash
ssh vanzai@220.158.28.35
nano /var/www/vanzai/.env
```

```env
OCR_UPLOAD_TOKEN_SECRET=<openssl rand -hex 32>
OCR_UPLOAD_SESSION_SECRET=<openssl rand -hex 32>
OCR_UPLOAD_IP_SECRET=<openssl rand -hex 32>
OCR_PUBLIC_PAYGATE_PRECHECK_ENABLED=true
```

未設定時は `JWT_SECRET_KEY` からフォールバックするが、本番では個別設定を推奨。

### 1-2. OCR ジョブワーカー（systemd）

**root で一度だけ**（SSH 鍵が無い場合は VPS プロバイダの Web コンソールから root ログイン）:

```bash
bash /var/www/vanzai/scripts/deploy/04_root_setup_systemd.sh
```

- `vanzai-ocr-worker` の systemd 有効化・起動
- `vanzai-api` の systemd 再起動
- `vanzai` ユーザー向け **パスワードなし sudo**（デプロイスクリプト用）

`vanzai` にパスワードなし sudo が無い場合の代替: デプロイスクリプトが **crontab**（@reboot + 5分監視）を自動設定済み（Ver.0.11.1〜）。

### 1-3. nginx（任意・推奨）

公開 URL の token が Referer に載らないよう、`/public/ocr-upload` に `Referrer-Policy: no-referrer` を設定。API レスポンスでも付与済み。

---

## 2. 日常運用

### 2-1. リンク発行（事務局）

1. 管理画面 → OCR（Paygate SS / 精算レシート）→ **外部アップロードリンク**
2. ラベル・有効期限・初期種別を設定して「リンクを発行」
3. 表示された URL をコピーして現場へ共有（**再表示不可** — 失効して再発行）

URL 形式: `https://vanzai-portal.com/public/ocr-upload?token=...`

### 2-2. 現場アップロード

1. 共有 URL を開く → セッション交換後、URL から token は消える
2. 画像種別（Paygate SS / 精算レシート）を選択
3. 画像をアップロード → **「受付完了」のみ表示**（OCR 結果は事務局画面）

**Paygate SS で決済方法なし** → 422、再アップロードを促す（best-effort OCR プレチェック）

### 2-3. 事務局での確認

- OCR 画面の画像一覧に **「外部」バッジ**（アップロード者名があれば併記）
- 重複は既存の OCR 判定画面で確認（同一 SHA256 は `reused_existing`）
- 解析はワーカーが非同期実行。`parse_status` が `pending` → `completed` / `failed`

---

## 3. デプロイ

```powershell
# ローカル
cd C:\VANZAI_project
git push origin feature/2026-03-31-next-work
```

```bash
# VPS（git pull / stash は不要）
ssh -i ~/.ssh/vanzai_vps vanzai@220.158.28.35 "bash /var/www/vanzai/scripts/deploy/02_app_deploy.sh"
```

**注意:** デプロイスクリプトは起動時に読み込まれるため、**ワーカー有効化（ステップ 7）は2回目のデプロイから**自動適用される。初回は 1-2 を手動実行。

sudo 不可で API 再起動がスキップされた場合:

```bash
ssh vanzai@220.158.28.35 "bash /var/www/vanzai/restart_uvicorn.sh"
```

### 動作確認

```bash
curl https://api.vanzai-portal.com/api/health
sudo systemctl status vanzai-api
sudo systemctl status vanzai-ocr-worker
pgrep -af run_job_worker   # ワーカー稼働確認
```

---

## 4. トラブルシュート

| 症状 | 確認・対処 |
|------|-----------|
| アップロード後ずっと `pending` | ワーカー停止 → `systemctl restart vanzai-ocr-worker` または nohup 再起動 |
| 410 / リンク無効 | 期限切れ or 失効 → 新規リンク発行 |
| 429 | レート制限（リンク 30/分、IP 60/分）または `max_upload_count` 到達 |
| 422 Paygate SS | 決済方法が写っていない画像 → 再撮影・アップロード |
| 415 HEIC | JPEG/PNG に変換して再アップロード |

---

## 5. ローカル開発環境の整理

OneDrive 等の同期で `*[conflicted]*` ファイルが出た場合:

```powershell
cd C:\VANZAI_project
git checkout HEAD -- apps/admin-web/package.json apps/admin-web/index.html apps/admin-web/src/components/SideNav.tsx
# 競合コピーは .gitignore で無視。手動削除可:
Remove-Item -Recurse -Force Backup, .tmp -ErrorAction SilentlyContinue
```

正本は常に **git の HEAD**（`feature/2026-03-31-next-work` の最新コミット）。
