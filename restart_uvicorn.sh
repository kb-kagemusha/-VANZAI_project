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
sleep 4
curl -s http://localhost:8000/api/worker/push/vapid-public-key -H 'Authorization: Bearer invalid'
