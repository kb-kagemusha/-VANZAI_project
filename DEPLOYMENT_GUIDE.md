# 実装・デプロイガイド（ステップ・バイ・ステップ）

## 前提条件
- ✅ Python 3.13.9 インストール済み
- ✅ 仮想環境 `.venv` 作成済み
- ✅ 全パッケージインストール済み（`pip install -e .`）
- ✅ Kintone アプリ作成済み

---

## ステップ1: 環境変数の設定

### 1.1 `.env` ファイルを作成
```powershell
cd C:\VANZAI_project
Copy-Item .env.example .env
code .env  # VS Codeで開く
```

### 1.2 必須設定を編集

**最小構成（ローカルテスト用）:**
```env
DATABASE_URL=sqlite:///./vanzai.db
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

**Kintone連携を使う場合:**
```env
KINTONE_SUBDOMAIN=your-company
# アプリ別トークン（必要なアプリ分だけ設定）
KINTONE_TOKEN_WORKERS=your-workers-token
KINTONE_TOKEN_PROJECTS=your-projects-token
KINTONE_TOKEN_ACTUALS=your-actuals-token
KINTONE_APP_WORKERS=1
KINTONE_APP_PROJECTS=2
KINTONE_APP_ACTUALS=3
# ... 他のアプリIDを実際の値に変更
```

**JWT認証を使う場合:**
```env
JWT_SECRET_KEY=your-generated-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

> **JWT_SECRET_KEY生成方法:**
> ```powershell
> C:/VANZAI_project/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

**メール送信を使う場合（Gmail例）:**
```env
EMAIL_DRY_RUN=false
EMAIL_PROVIDER=gmail
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_EMAIL=noreply@vanzai.com
SMTP_FROM_NAME=VANZAI System
```

> **Gmail App Password取得方法:**
> 1. Googleアカウント → セキュリティ → 2段階認証を有効化
> 2. アプリパスワード → 「メール」を選択 → パスワード生成
> 3. 生成された16桁のパスワードを `SMTP_PASSWORD` に設定

**スケジューラーを使う場合:**
```env
SCHEDULER_ENABLED=true
SCHEDULER_WEEKLY_DAY=0
SCHEDULER_WEEKLY_HOUR=9
SCHEDULER_DAILY_HOUR=6
SCHEDULER_MONTHLY_DAY=1
SCHEDULER_MONTHLY_HOUR=10
```

> **スケジューラー設定の意味:**
> - `SCHEDULER_WEEKLY_DAY`: 週次実行の曜日（0=月曜, 6=日曜）
> - `SCHEDULER_WEEKLY_HOUR`: 週次実行の時刻（0-23）
> - `SCHEDULER_DAILY_HOUR`: 日次実行の時刻（0-23）
> - `SCHEDULER_MONTHLY_DAY`: 月次実行の日（1-28）
> - `SCHEDULER_MONTHLY_HOUR`: 月次実行の時刻（0-23）

---

## ステップ2: データベースの初期化

### 2.1 マイグレーション実行（テーブル作成）
```powershell
# 現在のマイグレーション状態を確認
alembic current

# 最新バージョンまでマイグレーション実行
alembic upgrade head

# 確認: vanzai.db が作成されていることを確認
ls vanzai.db
```

**期待される出力:**
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Initial schema
INFO  [alembic.runtime.migration] Running upgrade 001_initial -> 002_pricing_billing, Add pricing and billing models
```

### 2.2 マイグレーション確認
```powershell
# 現在のバージョンを確認
alembic current
# 出力: 002_pricing_billing (head)

# 作成されたテーブルを確認（SQLiteの場合）
C:/VANZAI_project/.venv/Scripts/python.exe -c "import sqlite3; conn = sqlite3.connect('vanzai.db'); print('\n'.join([row[0] for row in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()]))"
```

**期待されるテーブル一覧:**
```
clients
workers
roles
projects
sites
assignments
shift_slots
actuals
price_sales
price_outsource
expenses
incentive_rules
incentives
invoices
invoice_lines
payouts
payout_lines
closing_periods
audit_log
import_batch
email_templates
```

---

## ステップ3: 初期データの投入

### 3.1 マスタデータCSVの準備

**方法A: Kintoneから同期（推奨）**
```python
# Pythonスクリプトで実行
from src.services.kintone_service import KintoneService
from src.models.base import get_db

db = next(get_db())
kintone = KintoneService()

# Workersを同期
workers_data = kintone.sync_workers(app_id=1)
print(f"同期完了: {len(workers_data)} 件")

# Projectsを同期
projects_data = kintone.sync_projects(app_id=2)
print(f"同期完了: {len(projects_data)} 件")
```

**方法B: CSVから直接インポート**
```powershell
# CSVインポートスクリプトを実行
C:/VANZAI_project/.venv/Scripts/python.exe scripts/import_master_data.py
```

### 3.2 初期データ投入スクリプト作成

`scripts/import_master_data.py` を作成:
```python
"""初期マスタデータ投入スクリプト"""
from sqlalchemy.orm import Session
from src.models.base import engine, Base
from src.models.master import Client, Worker, Role, Project, Site
from src.services.csv_import import CSVImportService
import os

def import_all_master_data():
    """すべてのマスタデータをCSVから投入"""
    Base.metadata.create_all(bind=engine)
    
    with Session(engine) as db:
        csv_service = CSVImportService(db)
        
        # クライアント
        print("クライアントをインポート中...")
        result = csv_service.import_clients("docs/kintone/csv/clients.csv")
        print(f"  成功: {result['imported']}, エラー: {result['errors']}")
        
        # 稼働者
        print("稼働者をインポート中...")
        result = csv_service.import_workers("kintone_app/workers_utf8.csv")
        print(f"  成功: {result['imported']}, エラー: {result['errors']}")
        
        # ロール
        print("ロールをインポート中...")
        result = csv_service.import_roles("docs/kintone/csv/roles.csv")
        print(f"  成功: {result['imported']}, エラー: {result['errors']}")
        
        # 案件
        print("案件をインポート中...")
        result = csv_service.import_projects("docs/kintone/csv/projects.csv")
        print(f"  成功: {result['imported']}, エラー: {result['errors']}")
        
        # サイト
        print("サイトをインポート中...")
        result = csv_service.import_sites("docs/kintone/csv/sites.csv")
        print(f"  成功: {result['imported']}, エラー: {result['errors']}")
        
        print("\n✅ マスタデータの投入が完了しました")

if __name__ == "__main__":
    import_all_master_data()
```

実行:
```powershell
C:/VANZAI_project/.venv/Scripts/python.exe scripts/import_master_data.py
```

---

## ステップ4: API起動とテスト

### 4.1 API起動
```powershell
cd C:\VANZAI_project

# 開発モード（自動リロード有効）
C:/VANZAI_project/.venv/Scripts/python.exe -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# または
uvicorn src.api.main:app --reload
```

**起動確認:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 4.2 Swagger UIでテスト

ブラウザで開く:
```
http://localhost:8000/api/docs
```

**確認すべきエンドポイント:**
- ✅ `GET /api/health` - ヘルスチェック
- ✅ `POST /api/auth/token` - JWT認証（OAuth2標準）
- ✅ `GET /api/auth/me` - 現在のユーザー情報取得
- ✅ `GET /api/dashboard` - ダッシュボード取得
- ✅ `POST /api/csv/upload` - CSV アップロード
- ✅ `POST /api/invoices/generate` - 請求書生成
- ✅ `POST /api/payouts/generate` - 支払明細生成

**動作確認テスト例:**
```bash
# ヘルスチェック
curl http://localhost:8000/api/health

# JWT認証（トークン取得）
curl -X POST "http://localhost:8000/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"

# ユーザー情報取得（認証必須）
curl "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# ダッシュボード取得
curl "http://localhost:8000/api/dashboard?period_key=202601"
```

### 4.3 Postmanでテスト（オプション）

OpenAPI定義をインポート:
```
http://localhost:8000/api/openapi.json
```

---

## ステップ5: 実際の運用フロー

### 5.1 週次運用（毎週）

**シフト予定の取り込み:**
```powershell
# CSVアップロード（Web UI経由）
# または API経由:
curl -X POST "http://localhost:8000/api/csv/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@shift_slots_202601.csv" \
  -F "entity_type=shift_slots"
```

**実績の取り込み（Kintone連携）:**
```python
# Pythonスクリプトで実行
from src.services.kintone_service import KintoneService
from datetime import date

kintone = KintoneService()
actuals = kintone.get_actuals(
    app_id=3,
    date_from=date(2026, 1, 20),
    date_to=date(2026, 1, 26)
)
print(f"取得: {len(actuals)} 件")
```

詳細は [RUNBOOK_WEEKLY.md](RUNBOOK_WEEKLY.md) を参照。

### 5.2 月次運用（毎月）

**締め処理 → 請求書・支払明細生成:**
```bash
# Soft Close（解除可能）
curl -X POST "http://localhost:8000/api/closing/soft" \
  -H "Content-Type: application/json" \
  -d '{"period_key": "202601", "close_type": "soft", "requested_by": "admin"}'

# 請求書一括生成
curl -X POST "http://localhost:8000/api/invoices/generate" \
  -H "Content-Type: application/json" \
  -d '{"period_key": "202601"}'

# 支払明細一括生成
curl -X POST "http://localhost:8000/api/payouts/generate" \
  -H "Content-Type: application/json" \
  -d '{"period_key": "202601"}'
```

詳細は [RUNBOOK_MONTHLY.md](RUNBOOK_MONTHLY.md) を参照。

---

## ステップ6: スケジューラーの起動（オプション）

### 6.1 スケジューラー有効化

`.env` で設定:
```env
SCHEDULER_ENABLED=true
SCHEDULER_WEEKLY_DAY=0        # 月曜日（0=月曜, 6=日曜）
SCHEDULER_WEEKLY_HOUR=9       # 9:00
SCHEDULER_DAILY_HOUR=6        # 6:00
SCHEDULER_MONTHLY_DAY=1       # 毎月1日
SCHEDULER_MONTHLY_HOUR=10     # 10:00
EMAIL_DRY_RUN=false           # 実際にメールを送信する場合
```

> **スケジューラーで自動実行されるジョブ:**
> - **週次催促メール**: 毎週月曜日 9:00（CSV未提出者に催促メール送信）
> - **日次ダッシュボード更新**: 毎日 6:00（未処理タスクのサマリー更新）
> - **月次請求書生成**: 毎月1日 10:00（請求書PDF生成 + 承認依頼メール送信）

### 6.2 バックグラウンドで実行

**方法A: スケジューラー専用プロセス**
```powershell
# scheduler_runner.py を実行
C:/VANZAI_project/.venv/Scripts/python.exe scripts/scheduler_runner.py
```

`scripts/scheduler_runner.py` の内容:
```python
"""スケジューラー実行スクリプト"""
from src.services.scheduler import get_scheduler, initialize_default_jobs
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    scheduler = get_scheduler()
  initialize_default_jobs()  # SCHEDULER_ENABLED=true のときのみ登録
    
    logger.info("✅ スケジューラー起動完了")
    logger.info("登録済みジョブ:")
    for job in scheduler.list_jobs():
        logger.info(f"  - {job['id']}: {job['next_run']}")
    
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("スケジューラー停止")

if __name__ == "__main__":
    main()
```

**方法B: API起動時に自動起動**

`src/api/main.py` に追加（既に実装済み）:
```python
from src.services.scheduler import get_scheduler, initialize_default_jobs

@app.on_event("startup")
async def startup_event():
  initialize_default_jobs()  # SCHEDULER_ENABLED=true のときのみ登録

@app.on_event("shutdown")
async def shutdown_event():
    get_scheduler().shutdown()
```

> **注意事項:**
> - スケジューラーは API と同一プロセスで動作します
> - `EMAIL_DRY_RUN=true` の場合、メールは送信されません（ログのみ）
> - ジョブ実行ログは `logs/scheduler.log` に出力されます

---

## ステップ7: テスト実行

### 7.1 全テスト実行
```powershell
# 全テスト実行
C:/VANZAI_project/.venv/Scripts/python.exe -m pytest -v

# カバレッジ付き
C:/VANZAI_project/.venv/Scripts/python.exe -m pytest --cov=src --cov-report=html
```

### 7.2 個別テスト実行
```powershell
# 時間計算テスト
pytest tests/test_time_calc.py -v

# CSV取り込みテスト
pytest tests/test_csv_import.py -v

# 請求書・支払テスト
pytest tests/test_invoice_payout.py -v

# 締め処理テスト
pytest tests/test_closing.py -v
```

**期待される結果:**
```
126 passed in 2.34s
```

---

## ステップ8: 本番環境へのデプロイ（オプション）

### 8.1 PostgreSQL使用（推奨）

`.env` 変更:
```env
DATABASE_URL=postgresql://vanzai_user:password@localhost:5432/vanzai_prod
```

マイグレーション実行:
```bash
alembic upgrade head
```

### 8.2 Systemdサービス化（Linux）

`/etc/systemd/system/vanzai-api.service`:
```ini
[Unit]
Description=VANZAI API Service
After=network.target

[Service]
Type=simple
User=vanzai
WorkingDirectory=/opt/vanzai
Environment="PATH=/opt/vanzai/.venv/bin"
ExecStart=/opt/vanzai/.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

起動:
```bash
sudo systemctl enable vanzai-api
sudo systemctl start vanzai-api
sudo systemctl status vanzai-api
```

### 8.3 Nginx リバースプロキシ（オプション）

`/etc/nginx/sites-available/vanzai`:
```nginx
server {
    listen 80;
    server_name vanzai.example.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'src'`
```powershell
# パッケージを編集可能モードでインストール
C:/VANZAI_project/.venv/Scripts/python.exe -m pip install -e .
```

### エラー: `alembic.util.exc.CommandError: Can't locate revision identified by '001_initial'`
```powershell
# マイグレーション履歴をクリア
rm vanzai.db
alembic upgrade head
```

### エラー: SMTP認証エラー
- Gmail: アプリパスワードを使用（通常パスワードは不可）
- SendGrid: `SMTP_USERNAME=apikey` に設定
- 2段階認証を確認

### Kintone接続エラー
```python
# 接続テスト
from src.services.kintone_service import KintoneService
kintone = KintoneService()
print(kintone.config.base_url)  # URLを確認
```

---

## チェックリスト

### 初回セットアップ
- [ ] `.env` ファイル作成・設定
- [ ] `alembic upgrade head` 実行
- [ ] マスタデータ投入（CSV or Kintone）
- [ ] API起動確認（`http://localhost:8000/api/docs`）
- [ ] テスト実行（`pytest -v`）

### 運用開始前
- [ ] SMTP設定テスト（メール送信確認）
- [ ] JWT認証テスト（トークン発行・検証）
- [ ] Kintone連携テスト（実績取得確認）
- [ ] 請求書PDF生成テスト（`./invoices/` 出力確認）
- [ ] 銀行振込ファイル生成テスト
- [ ] スケジューラージョブ確認（週次催促、月次請求書生成）

### 本番環境
- [ ] PostgreSQL移行
- [ ] バックアップ設定
- [ ] 監視・ログ設定
- [ ] SSL/TLS設定（Nginx）
- [ ] JWT秘密鍵の安全な管理（環境変数、KMS）
- [ ] 権限・認証設定（primary_manager/secondary_manager）

---

## 次のステップ

実装完了後、以下の拡張を検討:

1. **認証・認可**: JWT、OAuth2、ロールベースアクセス制御
2. **フロントエンド**: React/Vue.js、Streamlitダッシュボード
3. **通知機能**: Slack連携、LINE通知
4. **監査・監視**: Prometheus + Grafana、Sentry
5. **CI/CD**: GitHub Actions、自動テスト・デプロイ

詳細は [docs/ops/STATUS.md](docs/ops/STATUS.md) と [TASK_BACKLOG.md](TASK_BACKLOG.md) を参照。

---

**作成日**: 2026-01-27  
**バージョン**: 1.0  
**関連ドキュメント**: [DESIGN_SPEC_v0.3.md](docs/spec/DESIGN_SPEC_v0.3.md), [RUNBOOK_MONTHLY.md](RUNBOOK_MONTHLY.md)
