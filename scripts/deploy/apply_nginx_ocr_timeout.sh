#!/bin/bash
# nginx OCR用タイムアウト反映（root で実行）
set -euo pipefail

SRC="${1:-/tmp/vanzai_nginx_new.conf}"
DEST="/etc/nginx/sites-available/vanzai"

if [ "$(id -u)" -ne 0 ]; then
  echo "root で実行してください: sudo bash $0"
  exit 1
fi

if [ ! -f "$SRC" ]; then
  echo "設定ファイルがありません: $SRC"
  exit 1
fi

cp "$DEST" "${DEST}.bak.$(date +%Y%m%d%H%M%S)"
cp "$SRC" "$DEST"
nginx -t
systemctl reload nginx
echo "OK: proxy_read_timeout=$(grep proxy_read_timeout "$DEST" | head -1)"
