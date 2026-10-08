#!/bin/bash
# =============================================================================
# 03_frontend_only_deploy.sh — フロントエンドのみデプロイ（UI / favicon 向け）
# 実行場所: VPS上 (vanzai ユーザー)
# alembic / pip install をスキップし、ビルドのみ行う
# =============================================================================
set -euo pipefail

APP_DIR="/var/www/vanzai"
STAMP_DIR="${APP_DIR}/.deploy-stamps"

echo "=============================="
echo "  フロントエンドのみデプロイ"
echo "=============================="

build_app() {
  local name=$1
  local app_path="${APP_DIR}/apps/${name}"
  local lock_file="${app_path}/package-lock.json"
  local lock_stamp="${STAMP_DIR}/${name}-npm-lock.sha256"
  local lock_hash=""
  echo "[build] ${name}..."
  cd "${app_path}"
  mkdir -p "${STAMP_DIR}"
  if [ -f "${lock_file}" ]; then
    lock_hash=$(sha256sum "${lock_file}" | awk '{print $1}')
  fi
  if [ -d "${app_path}/node_modules" ] && [ -n "${lock_hash}" ] && [ -f "${lock_stamp}" ] && [ "$(cat "${lock_stamp}")" = "${lock_hash}" ]; then
    echo "[build] ${name}: package-lock に変更なし。npm ci を省略"
  else
    npm ci --silent
    if [ -n "${lock_hash}" ]; then
      printf '%s\n' "${lock_hash}" > "${lock_stamp}"
    fi
  fi
  VITE_API_BASE_URL=https://api.vanzai-portal.com npm run build
  echo "[build] ${name} OK"
}

build_app "admin-web"
build_app "staff-mobile"

echo ""
echo "完了。API 確認:"
curl -sf https://api.vanzai-portal.com/api/health && echo "" || echo "WARNING: API health failed — bash restart_uvicorn.sh を実行"
