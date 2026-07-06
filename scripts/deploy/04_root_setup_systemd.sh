#!/bin/bash
# =============================================================================
# 04_root_setup_systemd.sh — root で一度だけ実行
# OCR ワーカー systemd 常駐 + vanzai デプロイ用 sudo（任意）
#
# 使い方（VPS コンソールまたは root SSH）:
#   bash /var/www/vanzai/scripts/deploy/04_root_setup_systemd.sh
# =============================================================================
set -euo pipefail

APP_DIR="/var/www/vanzai"
SUDOERS_FILE="/etc/sudoers.d/vanzai-deploy"

if [ "$(id -u)" -ne 0 ]; then
  echo "root で実行してください: sudo bash $0"
  exit 1
fi

echo "[1/3] vanzai-ocr-worker.service をインストール..."
cp "${APP_DIR}/scripts/deploy/systemd/vanzai-ocr-worker.service" /etc/systemd/system/vanzai-ocr-worker.service
systemctl daemon-reload
systemctl enable vanzai-ocr-worker
systemctl restart vanzai-ocr-worker
sleep 1
systemctl status vanzai-ocr-worker --no-pager || true

echo "[2/3] vanzai-api を systemd で再起動..."
systemctl enable vanzai-api
systemctl restart vanzai-api
sleep 2
systemctl status vanzai-api --no-pager || true

echo "[3/3] vanzai ユーザー向け sudoers（デプロイ用・パスワード不要）..."
cat > "${SUDOERS_FILE}" <<'EOF'
# VANZAI deploy: allow vanzai to restart services without password
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl enable vanzai-api
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl restart vanzai-api
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl status vanzai-api
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl enable vanzai-ocr-worker
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl restart vanzai-ocr-worker
vanzai ALL=(ALL) NOPASSWD: /bin/systemctl status vanzai-ocr-worker
vanzai ALL=(ALL) NOPASSWD: /bin/cp /var/www/vanzai/scripts/deploy/systemd/vanzai-ocr-worker.service /etc/systemd/system/vanzai-ocr-worker.service
EOF
chmod 440 "${SUDOERS_FILE}"
visudo -c -f "${SUDOERS_FILE}"

echo ""
echo "完了。確認:"
echo "  systemctl is-active vanzai-ocr-worker"
echo "  systemctl is-active vanzai-api"
echo "  sudo -u vanzai sudo -n systemctl status vanzai-api"
