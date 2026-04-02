#!/bin/bash
# =============================================================================
# 02_app_deploy.sh — アプリデプロイスクリプト
# 実行場所: VPS上 (vanzai ユーザーで実行)
# 実行方法: bash /var/www/vanzai/scripts/deploy/02_app_deploy.sh
# 初回・更新時どちらでも使用可
# =============================================================================
set -euo pipefail

APP_DIR="/var/www/vanzai"
REPO_URL="https://github.com/kb-kagemusha/-VANZAI_project.git"
VENV_DIR="${APP_DIR}/.venv"

echo "=============================="
echo "  VANZAI アプリデプロイ開始"
echo "=============================="

CURRENT_BRANCH=""

# ----------------------------------------
# 1. コード取得（初回: clone / 更新: pull）
# ----------------------------------------
echo "[1/6] コード取得..."
if [ -d "${APP_DIR}/.git" ]; then
    echo "  git pull (更新)..."
    cd ${APP_DIR}
    CURRENT_BRANCH=$(git branch --show-current || true)
    if [ -z "${CURRENT_BRANCH}" ]; then
        CURRENT_BRANCH="main"
    fi
    git fetch origin
    if git show-ref --verify --quiet "refs/remotes/origin/${CURRENT_BRANCH}"; then
        git reset --hard "origin/${CURRENT_BRANCH}"
    else
        echo "  origin/${CURRENT_BRANCH} が見つからないため origin/main を使用します"
        git reset --hard origin/main
    fi
else
    echo "  git clone (初回)..."
    # 一時ディレクトリにcloneしてから移動
    TMP_DIR=$(mktemp -d)
    git clone ${REPO_URL} ${TMP_DIR}/repo
    cp -a ${TMP_DIR}/repo/. ${APP_DIR}/
    rm -rf ${TMP_DIR}
    cd ${APP_DIR}
    CURRENT_BRANCH=$(git branch --show-current || true)
fi
echo "  コード取得完了: $(git log --oneline -1)"

# ----------------------------------------
# 2. Python 仮想環境・依存パッケージ
# ----------------------------------------
echo "[2/6] Python 環境セットアップ..."
cd ${APP_DIR}

if [ ! -d "${VENV_DIR}" ]; then
    python3.12 -m venv ${VENV_DIR}
fi

${VENV_DIR}/bin/pip install --upgrade pip -q
${VENV_DIR}/bin/pip install psycopg2-binary -q
${VENV_DIR}/bin/pip install -e ".[dev]" -q
echo "  Python パッケージインストール完了"

# ----------------------------------------
# 3. .env ファイル確認
# ----------------------------------------
echo "[3/6] .env ファイル確認..."
if [ ! -f "${APP_DIR}/.env" ]; then
    echo ""
    echo "  !! .env ファイルがありません !!"
    echo "  以下を参考に作成してください:"
    echo ""
    echo "  nano ${APP_DIR}/.env"
    echo ""
    echo "  最低限必要な設定:"
    cat <<'EOF'
  DATABASE_URL=postgresql://vanzai_db:<password>@localhost:5432/vanzai_prod
  JWT_SECRET_KEY=<openssl rand -hex 32 で生成>
  JWT_ALGORITHM=HS256
  JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
  JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
  EMAIL_DRY_RUN=true
  KINTONE_SUBDOMAIN=xtf5wpxp3gk2
  KINTONE_GUEST_SPACE_ID=3
EOF
    echo ""
    echo "  .env 作成後、このスクリプトを再実行してください"
    exit 1
else
    echo "  .env ファイル確認OK"
fi

set -a
source "${APP_DIR}/.env"
set +a

# ----------------------------------------
# 4. DBマイグレーション
# ----------------------------------------
echo "[4/6] DBマイグレーション..."
cd ${APP_DIR}
${VENV_DIR}/bin/alembic upgrade head
echo "  マイグレーション完了"

# ----------------------------------------
# 5. フロントエンドビルド
# ----------------------------------------
echo "[5/6] フロントエンドビルド..."

# admin-web
echo "  admin-web ビルド中..."
cd ${APP_DIR}/apps/admin-web
npm ci --silent
VITE_API_BASE_URL=https://api.vanzai-portal.com npm run build

# staff-mobile
echo "  staff-mobile ビルド中..."
cd ${APP_DIR}/apps/staff-mobile
npm ci --silent
VITE_API_BASE_URL=https://api.vanzai-portal.com npm run build

echo "  フロントエンドビルド完了"

# ----------------------------------------
# 6. systemd サービス再起動
# ----------------------------------------
echo "[6/6] API サービス再起動..."
if sudo -n true 2>/dev/null; then
    sudo systemctl daemon-reload
    sudo systemctl enable vanzai-api
    sudo systemctl restart vanzai-api
    sleep 2
    sudo systemctl status vanzai-api --no-pager
else
    echo "  sudo にパスワードが必要なため、サービス再起動はスキップしました"
    echo "  root で以下を実行してください:"
    echo "    systemctl daemon-reload"
    echo "    systemctl enable vanzai-api"
    echo "    systemctl restart vanzai-api"
    echo "    systemctl status vanzai-api --no-pager"
fi

echo ""
echo "=============================="
echo "  デプロイ完了!"
echo "=============================="
echo ""
echo "動作確認:"
echo "  curl http://localhost:8000/health"
echo "  curl https://api.vanzai-portal.com/health"
