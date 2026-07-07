# VPS root 初回セットアップ（SSH 鍵 + systemd）

`vanzai` には SSH 鍵あり。`root` への **SSH パスワードログインは無効**（`Permission denied (publickey)`）のため、**vanzai で入ってから `su -`** する。

---

## 方法 A: vanzai 経由で root になる（推奨・今すぐできる）

### A-1. PowerShell で vanzai に接続

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35
```

- `-i` … 秘密鍵ファイルを指定（パスワード入力なしでログイン）
- 初回は `Are you sure you want to continue connecting (yes/no)?` → `yes`

`ssh root@...` だけだと鍵を送らないため **Permission denied (publickey)** になる。

### A-2. VPS 上で root に切り替え

```bash
su -
```

ここで **root パスワード**を入力（SSH ではなくサーバー内の切り替えなのでパスワードが効く）。

プロンプトが `root@...#` になれば OK。

### A-3. セットアップスクリプト実行

```bash
cd /var/www/vanzai
git fetch origin && git reset --hard origin/feature/2026-03-31-next-work
bash scripts/deploy/04_root_setup_systemd.sh
```

### A-4. 確認して抜ける

```bash
systemctl is-active vanzai-ocr-worker
systemctl is-active vanzai-api
exit          # root → vanzai
exit          # SSH 終了
```

---

## 方法 B: root に SSH 鍵を登録（以降 `ssh root@...` が使える）

方法 A の A-2 まで進んだあと、root シェルで:

```bash
mkdir -p /root/.ssh
chmod 700 /root/.ssh
nano /root/.ssh/authorized_keys
```

別の PowerShell ウィンドウで公開鍵を表示してコピー:

```powershell
Get-Content "$env:USERPROFILE\.ssh\vanzai_vps.pub"
```

`nano` に 1 行貼り付け → `Ctrl+O` Enter → `Ctrl+X`。

```bash
chmod 600 /root/.ssh/authorized_keys
exit
```

ローカル PowerShell で確認:

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" root@220.158.28.35 "whoami"
```

`root` と出れば、次回から:

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" root@220.158.28.35 "bash /var/www/vanzai/scripts/deploy/04_root_setup_systemd.sh"
```

---

## 方法 C（旧・通常は不可）: パスワードだけで root SSH

本 VPS はセキュリティ設定で **root の SSH パスワードログインは無効**。`ssh root@220.158.28.35` は鍵なしでは失敗する。

---

## 完了確認

```bash
systemctl is-active vanzai-ocr-worker
systemctl is-active vanzai-api
su - vanzai -c 'sudo -n systemctl status vanzai-api'
```

`sudo -n` がパスワードなしで通れば、以降の `02_app_deploy.sh` も API / ワーカー再起動まで自動化されます。
