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
# PaddleOCR 2.x と互換のある OpenCV 4.x（5.x は cv2.INTER_LINEAR 欠落で OCR 失敗）
OPENCV_HEADLESS_PIN="opencv-python-headless==4.10.0.84"

echo "=============================="
echo "  VANZAI アプリデプロイ開始"
echo "=============================="

CURRENT_BRANCH=""

# ----------------------------------------
# 1. コード取得（初回: clone / 更新: pull）
# ----------------------------------------
echo "[1/7] コード取得..."
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
echo "[2/7] Python 環境セットアップ..."
cd ${APP_DIR}

if [ ! -d "${VENV_DIR}" ]; then
    python3.12 -m venv ${VENV_DIR}
fi

${VENV_DIR}/bin/pip install --upgrade pip -q
${VENV_DIR}/bin/pip install psycopg2-binary -q
${VENV_DIR}/bin/pip install -e ".[dev]" -q
${VENV_DIR}/bin/pip install -e ".[ocr]" -q

# paddleocr の依存解決で OpenCV 5.x が入ることがある。5.x は PaddleOCR 2.x と非互換。
# 全 opencv 系を一度外し、4.x headless を強制再インストールして検証する。
${VENV_DIR}/bin/pip uninstall -y \
    opencv-contrib-python opencv-python \
    opencv-contrib-python-headless opencv-python-headless 2>/dev/null || true
${VENV_DIR}/bin/pip install --force-reinstall "${OPENCV_HEADLESS_PIN}"
${VENV_DIR}/bin/python - <<'PY'
import cv2

if not hasattr(cv2, "INTER_LINEAR"):
    raise SystemExit(
        f"opencv verify failed: cv2 has no INTER_LINEAR (file={getattr(cv2, '__file__', None)})"
    )
print(f"  opencv-python-headless OK: {cv2.__version__}")
PY
echo "  Python パッケージインストール完了"

# ----------------------------------------
# 3. .env ファイル確認
# ----------------------------------------
echo "[3/7] .env ファイル確認..."
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
  OCR_UPLOAD_TOKEN_SECRET=<openssl rand -hex 32 で生成>
  OCR_UPLOAD_SESSION_SECRET=<openssl rand -hex 32 で生成>
  OCR_UPLOAD_IP_SECRET=<openssl rand -hex 32 で生成>
  OCR_PUBLIC_PAYGATE_PRECHECK_ENABLED=true
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
echo "[4/7] DBマイグレーション..."
cd ${APP_DIR}
set -a
source "${APP_DIR}/.env"
set +a
${VENV_DIR}/bin/alembic upgrade head
echo "  マイグレーション完了"

# ----------------------------------------
# 5. フロントエンドビルド（旧アセット保持付き）
# ----------------------------------------
echo "[5/7] フロントエンドビルド..."

# 旧 JS/CSS を RETAIN_DAYS 日間保持する関数
# - ブラウザキャッシュに旧 index.html を持つユーザーが旧 JS を参照しても 404 にならない
# - 保持期間後は自動削除
RETAIN_DAYS=7
ARCHIVE_ROOT="${APP_DIR}/.asset-archive"

build_with_asset_retention() {
    local APP_NAME=$1
    local APP_PATH="${APP_DIR}/apps/${APP_NAME}"
    local DIST_ASSETS="${APP_PATH}/dist/assets"
    local ARCHIVE_DIR="${ARCHIVE_ROOT}/${APP_NAME}"

    mkdir -p "${ARCHIVE_DIR}"

    # ビルド前: 現 dist/assets の JS と CSS をアーカイブに待避（新規ファイルのみ追加）
    if [ -d "${DIST_ASSETS}" ]; then
        find "${DIST_ASSETS}" \( -name "*.js" -o -name "*.css" \) | while read -r f; do
            cp -n "$f" "${ARCHIVE_DIR}/" 2>/dev/null || true
        done
    fi

    # ビルド実行
    echo "  ${APP_NAME} ビルド中..."
    cd "${APP_PATH}"
    npm ci --silent
    VITE_API_BASE_URL=https://api.vanzai-portal.com npm run build

    # ビルド後: アーカイブの旧ファイルを dist/assets に復元（新ファイルは上書きしない）
    if [ -d "${ARCHIVE_DIR}" ]; then
        find "${ARCHIVE_DIR}" \( -name "*.js" -o -name "*.css" \) | while read -r f; do
            cp -n "$f" "${DIST_ASSETS}/" 2>/dev/null || true
        done
    fi

    # RETAIN_DAYS 以上前のアーカイブエントリを削除
    find "${ARCHIVE_DIR}" -type f -mtime "+${RETAIN_DAYS}" -delete 2>/dev/null || true

    echo "  ${APP_NAME} ビルド完了 (旧アセット ${RETAIN_DAYS}日保持中)"
}

build_with_asset_retention "admin-web"
build_with_asset_retention "staff-mobile"

echo "  フロントエンドビルド完了"

# ----------------------------------------
# 6. systemd サービス再起動
# ----------------------------------------
echo "[6/7] API サービス再起動..."
if sudo -n true 2>/dev/null; then
    sudo systemctl daemon-reload
    sudo systemctl enable vanzai-api
    sudo systemctl restart vanzai-api
    sleep 2
    sudo systemctl status vanzai-api --no-pager
else
    echo "  sudo にパスワードが必要なため、サービス再起動はスキップしました"
    echo "  以下を実行してください:"
    echo "    bash ${APP_DIR}/restart_uvicorn.sh"
fi

# ----------------------------------------
# 7. OCR ジョブワーカー
# ----------------------------------------
echo "[7/7] OCR ジョブワーカー..."
mkdir -p "${APP_DIR}/logs"
if sudo -n true 2>/dev/null; then
    sudo cp "${APP_DIR}/scripts/deploy/systemd/vanzai-ocr-worker.service" /etc/systemd/system/vanzai-ocr-worker.service
    sudo systemctl daemon-reload
    sudo systemctl enable vanzai-ocr-worker
    sudo systemctl restart vanzai-ocr-worker
    sleep 1
    sudo systemctl status vanzai-ocr-worker --no-pager || true
else
    echo "  sudo 不可のため OCR ワーカーの systemd 設定はスキップしました"
    echo "  手動で scripts/deploy/systemd/vanzai-ocr-worker.service を配置してください"
fi

echo ""
echo "=============================="
echo "  デプロイ完了!"
echo "=============================="
echo ""
echo "動作確認:"
echo "  curl http://localhost:8000/api/health"
echo "  curl https://api.vanzai-portal.com/api/health"
echo "  sudo systemctl status vanzai-ocr-worker"
