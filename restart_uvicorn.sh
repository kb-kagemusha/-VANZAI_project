#!/bin/bash
pkill -f 'uvicorn src.api.main' 2>/dev/null || true
sleep 2
cd /var/www/vanzai
set -a
. /var/www/vanzai/.env
set +a
echo "VAPID_PUBLIC_KEY length: ${#VAPID_PUBLIC_KEY}"
nohup .venv/bin/uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --workers 2 --log-level info --access-log >> /var/www/vanzai/logs/uvicorn.log 2>&1 &
echo "PID=$!"
ready=0
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != "1" ]; then
  echo "API が /api/health に応答しませんでした"
  exit 1
fi
echo "API の /api/health が応答しました"
curl -s -o /dev/null -w "vapid_http=%{http_code}\n" \
  http://127.0.0.1:8000/api/worker/push/vapid-public-key \
  -H "Authorization: Bearer invalid" || true
exit 0
