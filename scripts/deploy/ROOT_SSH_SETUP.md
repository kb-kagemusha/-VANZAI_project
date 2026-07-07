# VPS root 初回セットアップ（SSH 鍵 + systemd）

`vanzai` には SSH 鍵あり。`root` には鍵なし・パスワードログイン可、と想定。

---

## 方法 A: パスワードで root SSH（いちばん簡単）

PowerShell で対話的に（パスワード入力が求められる）:

```powershell
ssh root@220.158.28.35
```

ログイン後:

```bash
cd /var/www/vanzai
git fetch origin && git reset --hard origin/feature/2026-03-31-next-work
bash scripts/deploy/04_root_setup_systemd.sh
```

---

## 方法 B: root に vanzai と同じ鍵を登録（以降は自動化可）

### B-1. 公開鍵をコピー（ローカル）

```powershell
Get-Content "$env:USERPROFILE\.ssh\vanzai_vps.pub"
```

表示された 1 行（`ssh-ed25519 AAAA... vanzai-vps`）をコピー。

### B-2. vanzai 経由で root に登録

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" vanzai@220.158.28.35
```

VPS 上:

```bash
su -
# root パスワードを入力

mkdir -p /root/.ssh
chmod 700 /root/.ssh
nano /root/.ssh/authorized_keys
# 公開鍵 1 行を貼り付けて保存

chmod 600 /root/.ssh/authorized_keys
exit   # root を抜ける
exit   # SSH を抜ける
```

### B-3. root 鍵ログインの確認

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" root@220.158.28.35 "whoami"
```

`root` と表示されれば OK。続けて:

```powershell
ssh -i "$env:USERPROFILE\.ssh\vanzai_vps" root@220.158.28.35 "bash /var/www/vanzai/scripts/deploy/04_root_setup_systemd.sh"
```

---

## 完了確認

```bash
systemctl is-active vanzai-ocr-worker
systemctl is-active vanzai-api
su - vanzai -c 'sudo -n systemctl status vanzai-api'
```

`sudo -n` がパスワードなしで通れば、以降の `02_app_deploy.sh` も API / ワーカー再起動まで自動化されます。
