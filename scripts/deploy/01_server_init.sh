#!/bin/bash
# =============================================================================
# 01_server_init.sh — VPS初期設定スクリプト
# 実行場所: VPS上 (root ユーザーで実行)
# 実行方法: bash 01_server_init.sh
# =============================================================================
set -euo pipefail

VPS_USER="vanzai"
APP_DIR="/var/www/vanzai"
DB_NAME="vanzai_prod"
DB_USER="vanzai_db"

echo "=============================="
echo "  VANZAI VPS 初期設定開始"
echo "=============================="

# ----------------------------------------
# 1. システムアップデート
# ----------------------------------------
echo "[1/8] システムアップデート..."
apt-get update -qq
apt-get upgrade -y -qq

# ----------------------------------------
# 2. 必要パッケージインストール
# ----------------------------------------
echo "[2/8] 基本パッケージインストール..."
apt-get install -y -qq \
    curl wget git unzip build-essential \
    software-properties-common ca-certificates \
    ufw fail2ban

# Python 3.12
echo "  -> Python 3.12..."
add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1
apt-get update -qq
apt-get install -y -qq python3.12 python3.12-venv python3.12-dev

# Node.js 20 LTS
echo "  -> Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
apt-get install -y -qq nodejs

# nginx
echo "  -> nginx..."
apt-get install -y -qq nginx

# PostgreSQL 16
echo "  -> PostgreSQL 16..."
apt-get install -y -qq postgresql postgresql-contrib
# psycopg2用ライブラリ
apt-get install -y -qq libpq-dev

# Certbot (Let's Encrypt)
echo "  -> Certbot..."
apt-get install -y -qq certbot python3-certbot-nginx

echo "  インストール完了"
node --version
python3.12 --version
psql --version

# ----------------------------------------
# 3. vanzai ユーザー作成
# ----------------------------------------
echo "[3/8] ${VPS_USER} ユーザー作成..."
if id "${VPS_USER}" &>/dev/null; then
    echo "  ユーザー ${VPS_USER} は既に存在します"
else
    adduser --disabled-password --gecos "" ${VPS_USER}
    usermod -aG sudo ${VPS_USER}
    echo "  ユーザー ${VPS_USER} を作成しました"
fi

# SSH authorized_keys ディレクトリ準備
mkdir -p /home/${VPS_USER}/.ssh
chmod 700 /home/${VPS_USER}/.ssh
touch /home/${VPS_USER}/.ssh/authorized_keys
chmod 600 /home/${VPS_USER}/.ssh/authorized_keys
chown -R ${VPS_USER}:${VPS_USER} /home/${VPS_USER}/.ssh

# ----------------------------------------
# 4. アプリディレクトリ作成
# ----------------------------------------
echo "[4/8] アプリディレクトリ作成..."
mkdir -p ${APP_DIR}
mkdir -p ${APP_DIR}/storage
mkdir -p ${APP_DIR}/logs
chown -R ${VPS_USER}:${VPS_USER} ${APP_DIR}
echo "  ${APP_DIR} を作成しました"

# ----------------------------------------
# 5. PostgreSQL セットアップ
# ----------------------------------------
echo "[5/8] PostgreSQL セットアップ..."
systemctl start postgresql
systemctl enable postgresql

# パスワードをランダム生成
DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

# DB ユーザーと DB 作成
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')
\gexec
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

echo ""
echo "  ======================================================"
echo "  DB接続情報（後で .env に貼り付けてください）:"
echo "    DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
echo "  ======================================================"
echo ""

# DB接続情報をファイルに保存
cat > /root/db_credentials.txt <<EOF
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
EOF
chmod 600 /root/db_credentials.txt
echo "  /root/db_credentials.txt に保存しました"

# ----------------------------------------
# 6. UFW ファイアウォール設定
# ----------------------------------------
echo "[6/8] UFW ファイアウォール設定..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   comment 'SSH'
ufw allow 80/tcp   comment 'HTTP'
ufw allow 443/tcp  comment 'HTTPS'
ufw --force enable
ufw status
echo "  UFW 設定完了"

# ----------------------------------------
# 7. fail2ban 設定
# ----------------------------------------
echo "[7/8] fail2ban 設定..."
systemctl enable fail2ban
systemctl start fail2ban
echo "  fail2ban 起動完了"

# ----------------------------------------
# 8. nginx デフォルト設定削除・起動確認
# ----------------------------------------
echo "[8/8] nginx 設定..."
rm -f /etc/nginx/sites-enabled/default
systemctl enable nginx
systemctl start nginx
echo "  nginx 起動完了"

echo ""
echo "=============================="
echo "  初期設定完了!"
echo "=============================="
echo ""
echo "次のステップ:"
echo "  1. SSH公開鍵を追加:"
echo "     echo '<公開鍵>' >> /home/${VPS_USER}/.ssh/authorized_keys"
echo ""
echo "  2. SSH鍵確認後、パスワード認証を無効化:"
echo "     sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config"
echo "     systemctl restart sshd"
echo ""
echo "  3. vanzai ユーザーで再ログインしてデプロイスクリプトを実行:"
echo "     ssh vanzai@220.158.28.35"
echo "     bash /var/www/vanzai/scripts/deploy/02_app_deploy.sh"
echo ""
cat /root/db_credentials.txt
