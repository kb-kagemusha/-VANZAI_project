# VPSデプロイ手順書

VPS IP: `220.158.28.35`
ドメイン: `vanzai-portal.com`
GitHubリポジトリ: `https://github.com/kb-kagemusha/-VANZAI_project.git`

---

## STEP 1 — SSH公開鍵の生成（Windows ローカル）

PowerShellで実行：

```powershell
# SSH鍵生成（Ed25519）
ssh-keygen -t ed25519 -C "vanzai-vps" -f "$env:USERPROFILE\.ssh\vanzai_vps"

# 公開鍵を表示（後でコピーする）
Get-Content "$env:USERPROFILE\.ssh\vanzai_vps.pub"
```

---

## STEP 2 — VPSにSSH接続（rootで）

```powershell
ssh root@220.158.28.35
```

パスワードを入力してログイン。

---

## STEP 3 — サーバー初期設定スクリプト実行

VPS上（root）で実行：

```bash
# スクリプトを一時取得して実行
curl -fsSL https://raw.githubusercontent.com/kb-kagemusha/-VANZAI_project/main/scripts/deploy/01_server_init.sh | bash
```

**または** スクリプトをアップロードして実行：

```bash
# Windows側で実行（別のPowerShellウィンドウ）
scp C:\VANZAI_project\scripts\deploy\01_server_init.sh root@220.158.28.35:/root/
```

```bash
# VPS側で実行
bash /root/01_server_init.sh
```

完了後、表示された `DATABASE_URL` をメモしておく。

---

## STEP 4 — SSH公開鍵を登録

VPS上（root）で実行：

```bash
# STEP 1で表示された公開鍵を貼り付ける
echo "ssh-ed25519 AAAA...（ここに公開鍵を貼り付け）" >> /home/vanzai/.ssh/authorized_keys
```

確認：

```powershell
# Windows側で SSH鍵認証をテスト
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35
```

ログインできたらパスワード認証を無効化：

```bash
# VPS上（root）
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

---

## STEP 5 — nginx・systemd設定ファイルを配置

Windows側で実行：

```powershell
# nginx設定
scp -i "$env:USERPROFILE\.ssh\vanzai_vps" `
    C:\VANZAI_project\scripts\deploy\nginx\vanzai.conf `
    vanzai@220.158.28.35:/tmp/

# systemdサービスファイル
scp -i "$env:USERPROFILE\.ssh\vanzai_vps" `
    C:\VANZAI_project\scripts\deploy\systemd\vanzai-api.service `
    vanzai@220.158.28.35:/tmp/
```

VPS上（sudo）で実行：

```bash
sudo cp /tmp/vanzai.conf /etc/nginx/sites-available/vanzai
sudo ln -sf /etc/nginx/sites-available/vanzai /etc/nginx/sites-enabled/vanzai
sudo nginx -t && sudo systemctl reload nginx

sudo cp /tmp/vanzai-api.service /etc/systemd/system/vanzai-api.service
sudo systemctl daemon-reload
```

---

## STEP 6 — アプリをデプロイ

VPS上（vanzai ユーザー）で実行：

```bash
# アプリディレクトリに移動
cd /var/www/vanzai

# コードをclone
git clone https://github.com/kb-kagemusha/-VANZAI_project.git .
```

> リポジトリがプライベートの場合: GitHubのSettings → Developer settings → Personal access tokens → Fine-grained tokens で読み取りトークンを作成し、URLに含める:
> `git clone https://<TOKEN>@github.com/kb-kagemusha/-VANZAI_project.git .`

---

## STEP 7 — .env ファイルを作成

VPS上（vanzai）で実行：

```bash
# STEP 3のDB情報と、JWTキーを生成して設定
JWT_KEY=$(openssl rand -hex 32)
DB_INFO=$(cat /root/db_credentials.txt | grep DATABASE_URL | cut -d= -f2-)

# DB情報をroot→vanzaiユーザーで確認（rootで実行）
sudo cat /root/db_credentials.txt

# .envを作成
nano /var/www/vanzai/.env
```

`env.production.template` の内容を参考に、以下を設定：
- `DATABASE_URL` ← `/root/db_credentials.txt` の値
- `JWT_SECRET_KEY` ← `openssl rand -hex 32` の出力
- Kintoneトークン ← ローカルの `.env` から転記

---

## STEP 8 — デプロイスクリプト実行

VPS上（vanzai）で実行：

```bash
bash /var/www/vanzai/scripts/deploy/02_app_deploy.sh
```

---

## STEP 9 — SSL証明書取得

DNS反映を確認してから（`nslookup vanzai-portal.com` で `220.158.28.35` が返ること）：

VPS上（root）で実行：

```bash
# メールアドレスを書き換えてから実行
bash /var/www/vanzai/scripts/deploy/03_ssl_setup.sh
```

---

## STEP 10 — 動作確認

```bash
# APIヘルスチェック
curl https://api.vanzai-portal.com/health

# サービス状態
sudo systemctl status vanzai-api
sudo systemctl status nginx

# ログ確認
tail -f /var/www/vanzai/logs/api.log
```

ブラウザで確認：
- https://vanzai-portal.com （管理画面）
- https://staff.vanzai-portal.com （スタッフ画面）
- https://api.vanzai-portal.com/docs （APIドキュメント）

---

## 更新デプロイ（2回目以降）

```powershell
# Windows側でコードをpush
cd C:\VANZAI_project
git push origin main
```

```bash
# VPS側で更新
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35
bash /var/www/vanzai/scripts/deploy/02_app_deploy.sh
```

---

## Windows側 SSH設定ファイル（楽に接続するため）

`C:\Users\<ユーザー名>\.ssh\config` に追記：

```
Host vanzai-vps
    HostName 220.158.28.35
    User vanzai
    IdentityFile ~/.ssh/vanzai_vps
```

設定後は `ssh vanzai-vps` だけで接続できる。
