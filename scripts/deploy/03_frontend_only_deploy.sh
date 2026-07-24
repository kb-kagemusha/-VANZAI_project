#!/bin/bash
# =============================================================================
# 03_frontend_only_deploy.sh — フロントエンドのみデプロイ（UI / favicon 向け）
# 実行場所: VPS上 (vanzai ユーザー)
# alembic / pip install をスキップし、ビルドのみ行う
# =============================================================================
set -euo pipefail

APP_DIR="/var/www/vanzai"

echo "=============================="
echo "  フロントエンドのみデプロイ"
echo "=============================="

build_app() {
  local name=$1
  echo "[build] ${name}..."
  cd "${APP_DIR}/apps/${name}"
  npm ci --silent
  VITE_API_BASE_URL=https://api.vanzai-portal.com npm run build
  echo "[build] ${name} OK"
}

build_app "admin-web"
build_app "staff-mobile"

echo ""
echo "完了。API 確認:"
curl -sf https://api.vanzai-portal.com/api/health && echo "" || echo "WARNING: API health failed — bash restart_uvicorn.sh を実行"
