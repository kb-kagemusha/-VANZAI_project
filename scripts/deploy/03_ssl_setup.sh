#!/bin/bash
# =============================================================================
# 03_ssl_setup.sh — Let's Encrypt SSL証明書取得
# 実行場所: VPS上 (root ユーザーで実行)
# 実行タイミング: DNS反映確認後 (nslookupでVPS IPが返ってから)
# 実行方法: bash 03_ssl_setup.sh
# =============================================================================
set -euo pipefail

DOMAIN="vanzai-portal.com"
EMAIL="admin@vanzai-portal.com"   # ← 実際のメールアドレスに変更

echo "=============================="
echo "  SSL証明書取得"
echo "=============================="

echo "DNS反映確認中..."
RESOLVED=$(dig +short ${DOMAIN} 2>/dev/null || nslookup ${DOMAIN} 2>/dev/null | grep -A1 'Name:' | grep 'Address' | awk '{print $2}')
echo "  ${DOMAIN} → ${RESOLVED}"

if [ "${RESOLVED}" != "220.158.28.35" ]; then
    echo ""
    echo "  !! DNS未反映または不一致 !!"
    echo "  期待値: 220.158.28.35"
    echo "  実際値: ${RESOLVED}"
    echo ""
    echo "  DNS反映後に再実行してください"
    exit 1
fi

echo "  DNS確認OK"
echo ""

# nginx設定ファイルをコピー（02_app_deploy.sh 実行後に行う）
if [ ! -f "/etc/nginx/sites-available/vanzai" ]; then
    cp /var/www/vanzai/scripts/deploy/nginx/vanzai.conf /etc/nginx/sites-available/vanzai
    ln -sf /etc/nginx/sites-available/vanzai /etc/nginx/sites-enabled/vanzai
    nginx -t
    systemctl reload nginx
    echo "  nginx設定適用完了"
fi

# 証明書取得
echo "証明書取得中..."
certbot --nginx \
    --non-interactive \
    --agree-tos \
    --email "${EMAIL}" \
    --redirect \
    -d ${DOMAIN} \
    -d www.${DOMAIN} \
    -d api.${DOMAIN} \
    -d staff.${DOMAIN}

echo ""
echo "=============================="
echo "  SSL設定完了!"
echo "=============================="
echo ""
echo "自動更新確認:"
certbot renew --dry-run
echo ""
echo "アクセス確認:"
echo "  https://vanzai-portal.com"
echo "  https://api.vanzai-portal.com/health"
echo "  https://staff.vanzai-portal.com"
