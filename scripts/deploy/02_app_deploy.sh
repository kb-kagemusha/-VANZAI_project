#!/bin/bash
# =============================================================================
# 02_app_deploy.sh — アプリデプロイスクリプト
# 実行場所: VPS上 (vanzai ユーザーで実行)
# 実行方法: bash /var/www/vanzai/scripts/deploy/02_app_deploy.sh
# 初回・更新時どちらでも使用可
# =============================================================================
set -euo pipefail

# 明示した場合だけ、2026年10・11月のダミー依頼を確認／作成する。
# 通常デプロイはデータに触れない。自己更新で再実行するときも引数を保持する。
CALENDAR_DEMO_ACTION="${1:-}"
case "${CALENDAR_DEMO_ACTION}" in
    ""|--operator-bind-login-preview|--operator-bind-login-apply|--operator-menu-status|--operator-menu-sync|--operator-menu-publish|--operator-menu-republish|--wake-monitor|--wake-monitor-status|--operator-menu-disable|--calendar-demo-preview|--calendar-demo-apply|--calendar-demo-tune|--calendar-demo-enrich|--restore-test-account-name|--calendar-demo-directors|--legacy-samples-preview|--legacy-samples-remove|--demo-incentives-preview|--demo-incentives-apply|--archived-demo-schedules-preview|--archived-demo-schedules-repair|--demo-schedule-gaps-preview|--demo-schedule-gaps-repair) ;;
    *) echo "不明なデプロイ引数"; exit 2 ;;
esac

APP_DIR="/var/www/vanzai"
REPO_URL="https://github.com/kb-kagemusha/-VANZAI_project.git"
VENV_DIR="${APP_DIR}/.venv"
STAMP_DIR="${APP_DIR}/.deploy-stamps"
# PaddleOCR 2.x と互換のある OpenCV 4.x（5.x は cv2.INTER_LINEAR 欠落で OCR 失敗）
OPENCV_HEADLESS_PIN="opencv-python-headless==4.10.0.84"

# 明示オプションはデプロイ済みコードで行う単独運用モード。
# 実行設定の内部読み込みのみ、2026-10-23ユーザー承認。値の表示・変更は禁止。
# git取得・ビルド・マイグレーション・サービス再起動・cron更新は行わない。
if [ -n "${CALENDAR_DEMO_ACTION}" ]; then
    cd "${APP_DIR}"
    set -a
    source "${APP_DIR}/.env"
    set +a
    if [ "${CALENDAR_DEMO_ACTION}" = "--operator-bind-login-preview" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/bind_operator_login.py" --staff-name "${2:?staff name required}" --username "${3:?login required}"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--operator-bind-login-apply" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/bind_operator_login.py" --staff-name "${2:?staff name required}" --username "${3:?login required}" --apply
    elif [ "${CALENDAR_DEMO_ACTION}" = "--operator-menu-disable" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" disable
    elif [ "${CALENDAR_DEMO_ACTION}" = "--operator-menu-status" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" status
    elif [ "${CALENDAR_DEMO_ACTION}" = "--operator-menu-sync" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" sync
    elif [ "${CALENDAR_DEMO_ACTION}" = "--operator-menu-publish" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" publish
    elif [ "${CALENDAR_DEMO_ACTION}" = "--wake-monitor-status" ]; then
        # Read-only: no monitor run, LINE sends, data writes or deployment.
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/wake_monitor.py" --status
    elif [ "${CALENDAR_DEMO_ACTION}" = "--wake-monitor" ]; then
        # 0.54.0（DEC-126）：起床の監視（毎分）。本人への催促・運営への知らせ
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/wake_monitor.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--operator-menu-republish" ]; then
        # 0.53.8（DEC-125）：公開中の個人別メニューを新しい6分割へ差し替える。全員の既定メニューは変えない
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" republish
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" status
    elif [ "${CALENDAR_DEMO_ACTION}" = "--calendar-demo-preview" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/seed_calendar_demo.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--demo-schedule-gaps-preview" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/repair_demo_schedule_gaps.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--demo-schedule-gaps-repair" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/repair_demo_schedule_gaps.py" --apply
    elif [ "${CALENDAR_DEMO_ACTION}" = "--archived-demo-schedules-preview" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/repair_archived_demo_schedules.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--archived-demo-schedules-repair" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/repair_archived_demo_schedules.py" --apply
    elif [ "${CALENDAR_DEMO_ACTION}" = "--demo-incentives-preview" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/enable_demo_incentives.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--demo-incentives-apply" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/enable_demo_incentives.py" --apply
    elif [ "${CALENDAR_DEMO_ACTION}" = "--legacy-samples-preview" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/remove_legacy_samples.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--legacy-samples-remove" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/remove_legacy_samples.py" --apply
    elif [ "${CALENDAR_DEMO_ACTION}" = "--calendar-demo-directors" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/tag_demo_directors.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--restore-test-account-name" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/restore_test_account_name.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--calendar-demo-enrich" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/enrich_calendar_demo.py"
    elif [ "${CALENDAR_DEMO_ACTION}" = "--calendar-demo-tune" ]; then
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/tune_calendar_demo.py"
    else
        "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/seed_calendar_demo.py" --apply
    fi
    exit 0
fi

echo "=============================="
echo "  VANZAI アプリデプロイ開始"
echo "=============================="

CURRENT_BRANCH=""

# ----------------------------------------
# 1. コード取得（初回: clone / 更新: pull）
# ----------------------------------------
echo "[1/7] コード取得..."
SCRIPT_PATH="${APP_DIR}/scripts/deploy/02_app_deploy.sh"
SCRIPT_HASH_BEFORE=""
if [ -f "${SCRIPT_PATH}" ]; then
    SCRIPT_HASH_BEFORE=$(sha256sum "${SCRIPT_PATH}" | awk '{print $1}')
fi
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

# デプロイ手順そのものが変わったときだけ、新しいスクリプトでやり直す。
SCRIPT_HASH_AFTER=$(sha256sum "${SCRIPT_PATH}" | awk '{print $1}')
if [ -n "${SCRIPT_HASH_BEFORE}" ] && [ "${SCRIPT_HASH_BEFORE}" != "${SCRIPT_HASH_AFTER}" ] && [ "${VANZAI_DEPLOY_REEXEC:-0}" != "1" ]; then
    export VANZAI_DEPLOY_REEXEC=1
    exec bash "${SCRIPT_PATH}" "$@"
fi

# ----------------------------------------
# 2. Python 仮想環境・依存パッケージ
# pyproject.toml と導入済みの OpenCV が同じなら、PyPI へ取りに行かない。
# 本番には dev（pytest / ruff）を入れない。
# ----------------------------------------
echo "[2/7] Python 環境セットアップ..."
cd ${APP_DIR}
mkdir -p "${STAMP_DIR}"

python_deps_ok() {
    [ -x "${VENV_DIR}/bin/python" ] || return 1
    [ -f "${STAMP_DIR}/pyproject.sha256" ] || return 1
    [ "$(cat "${STAMP_DIR}/pyproject.sha256")" = "$(sha256sum "${APP_DIR}/pyproject.toml" | awk '{print $1}')" ] || return 1
    "${VENV_DIR}/bin/python" - <<'PY'
import sys
from importlib.metadata import distributions

names = set()
for dist in distributions():
    name = (dist.metadata.get("Name") or "").lower()
    if name:
        names.add(name)
forbidden = {"opencv-python", "opencv-contrib-python", "opencv-contrib-python-headless"}
if names & forbidden:
    sys.exit(1)
for module_name in ("fastapi", "psycopg2", "cv2"):
    __import__(module_name)
import cv2
if not str(getattr(cv2, "__version__", "")).startswith("4.10."):
    sys.exit(1)
if not hasattr(cv2, "INTER_LINEAR"):
    sys.exit(1)
PY
}

repair_opencv() {
    echo "  OpenCV を 4.10 headless に揃えます"
    ${VENV_DIR}/bin/pip uninstall -y \
        opencv-contrib-python opencv-python \
        opencv-contrib-python-headless opencv-python-headless >/dev/null 2>&1 || true
    ${VENV_DIR}/bin/pip install "${OPENCV_HEADLESS_PIN}"
    ${VENV_DIR}/bin/python - <<'PY'
import cv2

if not hasattr(cv2, "INTER_LINEAR"):
    raise SystemExit(
        f"opencv verify failed: cv2 has no INTER_LINEAR (file={getattr(cv2, '__file__', None)})"
    )
print(f"  opencv-python-headless OK: {cv2.__version__}")
PY
}

if [ ! -d "${VENV_DIR}" ]; then
    python3.12 -m venv ${VENV_DIR}
fi

if python_deps_ok; then
    echo "  Python 依存は変更なし。パッケージの再取得は省略"
else
    ${VENV_DIR}/bin/pip install --upgrade pip -q
    ${VENV_DIR}/bin/pip install psycopg2-binary -q
    ${VENV_DIR}/bin/pip install -e . -q
    ${VENV_DIR}/bin/pip install -e ".[ocr]" -q
    # paddleocr の依存解決で OpenCV 5.x が入ることがある。導入したときだけ 4.x に戻す。
    repair_opencv
    sha256sum "${APP_DIR}/pyproject.toml" | awk '{print $1}' > "${STAMP_DIR}/pyproject.sha256"
fi

# 本番にテスト実行系を残さない。未導入ならすぐ終わる。
${VENV_DIR}/bin/pip uninstall -y pytest pytest-cov ruff >/dev/null 2>&1 || true
echo "  Python 環境確認完了"

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

# Existing secrets are managed separately; deployment never appends to .env.

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

    # ビルド実行。lockfile が同じなら npm ci はしない（中身の検証は lock の更新時に npm ci が行う）。
    echo "  ${APP_NAME} ビルド中..."
    cd "${APP_PATH}"
    local LOCK_FILE="${APP_PATH}/package-lock.json"
    local LOCK_STAMP="${STAMP_DIR}/${APP_NAME}-npm-lock.sha256"
    local LOCK_HASH=""
    if [ -f "${LOCK_FILE}" ]; then
        LOCK_HASH=$(sha256sum "${LOCK_FILE}" | awk '{print $1}')
    fi
    if [ -d "${APP_PATH}/node_modules" ] && [ -n "${LOCK_HASH}" ] && [ -f "${LOCK_STAMP}" ] && [ "$(cat "${LOCK_STAMP}")" = "${LOCK_HASH}" ]; then
        echo "  ${APP_NAME}: package-lock に変更なし。npm ci を省略"
    else
        npm ci --silent
        if [ -n "${LOCK_HASH}" ]; then
            printf '%s\n' "${LOCK_HASH}" > "${LOCK_STAMP}"
        fi
    fi
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
wait_for_api() {
    local attempt
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
            echo "  API の /api/health が応答しました"
            return 0
        fi
        sleep 2
    done
    echo "  API が /api/health に応答しませんでした"
    return 1
}

ocr_worker_running() {
    ps -u vanzai -o cmd= | grep -q '[r]un_job_worker.py'
}

echo "[6/7] API サービス再起動..."
if sudo -n true 2>/dev/null; then
    sudo systemctl daemon-reload
    sudo systemctl enable vanzai-api
    sudo systemctl restart vanzai-api
    sudo systemctl status vanzai-api --no-pager
else
    echo "  sudo にパスワードが必要なため、restart_uvicorn.sh で再起動します"
    bash "${APP_DIR}/restart_uvicorn.sh"
fi
wait_for_api

# ----------------------------------------
# 7. OCR ジョブワーカー
# ----------------------------------------
echo "[7/7] OCR ジョブワーカー..."
mkdir -p "${APP_DIR}/logs"
OCR_WORKER_STARTED=0
if sudo -n true 2>/dev/null; then
    sudo cp "${APP_DIR}/scripts/deploy/systemd/vanzai-ocr-worker.service" /etc/systemd/system/vanzai-ocr-worker.service
    sudo systemctl daemon-reload
    sudo systemctl enable vanzai-ocr-worker
    sudo systemctl restart vanzai-ocr-worker
    sleep 1
    sudo systemctl status vanzai-ocr-worker --no-pager || true
    OCR_WORKER_STARTED=1
else
    echo "  sudo 不可 — crontab でワーカー常駐を設定します"
    CRON_MARKER="# vanzai-ocr-worker"
    CRON_BOOT="${CRON_MARKER} @reboot sleep 30 && cd ${APP_DIR} && ${VENV_DIR}/bin/python ${APP_DIR}/scripts/ocr/run_job_worker.py >> ${APP_DIR}/logs/ocr-worker.log 2>> ${APP_DIR}/logs/ocr-worker-error.log"
    CRON_WATCH="${CRON_MARKER} */5 * * * * ps -u vanzai -o cmd= | grep -q '[r]un_job_worker.py' || (cd ${APP_DIR} && nohup ${VENV_DIR}/bin/python ${APP_DIR}/scripts/ocr/run_job_worker.py >> ${APP_DIR}/logs/ocr-worker.log 2>> ${APP_DIR}/logs/ocr-worker-error.log &)"
    (crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" || true
     echo "${CRON_BOOT}"
     echo "${CRON_WATCH}") | crontab -
    if ! ocr_worker_running; then
        nohup "${VENV_DIR}/bin/python" "${APP_DIR}/scripts/ocr/run_job_worker.py" \
            >> "${APP_DIR}/logs/ocr-worker.log" 2>> "${APP_DIR}/logs/ocr-worker-error.log" &
        sleep 1
    fi
    if ocr_worker_running; then
        echo "  OCR ワーカーは起動しています"
        ps -u vanzai -o pid=,cmd= | grep '[r]un_job_worker.py'
        OCR_WORKER_STARTED=1
    else
        echo "  !! OCR ワーカーが起動していません"
        exit 1
    fi
fi

echo "  受領期限の案内..."
mkdir -p "${APP_DIR}/logs"
REMIND_MARKER="# vanzai-order-ack-reminder"
REMIND_CRON="${REMIND_MARKER} 15 * * * * cd ${APP_DIR} && ${VENV_DIR}/bin/python ${APP_DIR}/scripts/line/remind_order_acks.py >> ${APP_DIR}/logs/order-ack-reminder.log 2>&1"
(crontab -l 2>/dev/null | grep -v "${REMIND_MARKER}" || true
 echo "${REMIND_CRON}") | crontab -

# Operator menus are personal only. The global worker menu is never changed.
"${VENV_DIR}/bin/python" "${APP_DIR}/scripts/line/operator_menu.py" publish
WAKE_MONITOR_MARKER="# vanzai-wake-monitor"
WAKE_MONITOR_CRON="* * * * * bash ${APP_DIR}/scripts/deploy/02_app_deploy.sh --wake-monitor >> ${APP_DIR}/logs/wake-monitor.log 2>&1 ${WAKE_MONITOR_MARKER}"
(crontab -l 2>/dev/null | grep -v "${WAKE_MONITOR_MARKER}" || true
 echo "${WAKE_MONITOR_CRON}") | crontab -
OPERATOR_MENU_MARKER="# vanzai-operator-menu-sync"
OPERATOR_MENU_CRON="* * * * * bash ${APP_DIR}/scripts/deploy/02_app_deploy.sh --operator-menu-sync >> ${APP_DIR}/logs/operator-menu-sync.log 2>&1 ${OPERATOR_MENU_MARKER}"
(crontab -l 2>/dev/null | grep -v "${OPERATOR_MENU_MARKER}" || true
 echo "${OPERATOR_MENU_CRON}") | crontab -

echo ""
echo "=============================="
echo "  デプロイ完了!"
echo "=============================="
echo ""
echo "動作確認:"
echo "  curl http://localhost:8000/api/health"
echo "  curl https://api.vanzai-portal.com/api/health"
if [ "${OCR_WORKER_STARTED:-0}" = "1" ]; then
    echo "  pgrep -af run_job_worker"
else
    echo "  sudo systemctl status vanzai-ocr-worker"
fi
