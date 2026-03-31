# クイックリファレンス - VANZAI Project

## 🎯 よく使うコマンド

### 環境起動
```powershell
# 仮想環境有効化
.venv\Scripts\Activate.ps1

# APIサーバー起動
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# ブラウザでSwagger UI開く
start http://localhost:8000/api/docs
```

### データベース操作
```powershell
# マイグレーション適用
alembic upgrade head

# 現在のリビジョン確認
alembic current

# マスタデータ再投入（DB削除→再作成）
Remove-Item vanzai.db
alembic upgrade head
python scripts/import_master_data.py
```

### テスト実行
```powershell
# 全テスト実行
pytest -v

# 特定のテスト実行
pytest tests/test_csv_import.py -v

# カバレッジ付き
pytest --cov=src --cov-report=html
```

---

## 📁 重要ファイルの場所

### 環境設定
- `.env` - 環境変数（Kintone設定、SMTP設定など）
- `.env.example` - 環境変数テンプレート
- `pyproject.toml` - Python依存関係

### データベース
- `vanzai.db` - SQLiteデータベース（458KB）
- `alembic/versions/` - マイグレーションスクリプト
- `alembic.ini` - Alembic設定

### ソースコード
- `src/models/` - データモデル
  - `base.py` - Base、Mixin
  - `enums.py` - Enum定義
  - `master.py` - マスタモデル
  - `transaction.py` - トランザクションモデル
- `src/services/` - ビジネスロジック
- `src/api/` - APIエンドポイント
  - `main_simple.py` - 簡易版（動作確認済み）
  - `main.py` - 完全版（要修正）

### ドキュメント
- `README.md` - プロジェクト概要
- `DEPLOYMENT_GUIDE.md` - デプロイメント手順
- `docs/DEPLOYMENT_COMPLETION_2026-01-27.md` - **構築完了レポート**
- `docs/FILE_INDEX.md` - **ファイル一覧と依存関係**
- `docs/spec/DESIGN_SPEC_v0.3.md` - **仕様の正本**
- `RUNBOOK_MONTHLY.md` - 月次運用手順

---

## 🔍 トラブルシューティング

### ImportError: cannot import name 'engine'
```powershell
# ❌ 間違い
from src.models.base import engine, SessionLocal

# ✅ 正しい
from src.api.deps import engine, SessionLocal
```

### AttributeError: モデルにフィールドがない
モデル定義を確認:
```powershell
# Clientモデルのフィールド確認
grep "class Client" src/models/master.py -A 20
```

よくある間違い:
- `billing_address` → `address`
- `billing_contact` → `contact_name`
- `Worker.code` → 存在しない
- `Project.status` → 存在しない

### サービスクラスが見つからない
実装形式を確認:
```powershell
# クラス形式: CsvImportService, AuditService
from src.services.csv_import import CsvImportService
service = CsvImportService(db)

# 関数形式: invoice_service, payout_service
from src.services import invoice_service
invoice_service.generate_invoice(db, ...)
```

### APIサーバーが起動しない
```powershell
# エラーログ確認
uvicorn src.api.main:app --reload

# Pythonプロセス確認
Get-Process | Where-Object {$_.ProcessName -eq "python"}

# ポート使用確認
netstat -ano | findstr :8000
```

---

## 📊 データ確認

### SQLiteでデータ確認
```powershell
# SQLite CLI起動
sqlite3 vanzai.db

# テーブル一覧
.tables

# データ件数確認
SELECT 'clients' as table_name, COUNT(*) as count FROM clients
UNION ALL
SELECT 'workers', COUNT(*) FROM workers
UNION ALL
SELECT 'projects', COUNT(*) FROM projects;

# 終了
.exit
```

### Python REPLでデータ確認
```python
from src.api.deps import SessionLocal
from src.models.master import Client, Worker
from src.models.transaction import Project

db = SessionLocal()

# クライアント一覧
clients = db.query(Client).all()
for c in clients:
    print(f"{c.code}: {c.name}")

# 稼働者一覧
workers = db.query(Worker).all()
for w in workers:
    print(f"{w.name} ({w.email})")

db.close()
```

---

## 🔗 主要エンドポイント

### APIサーバー（main_simple.py）
- `GET /` - ルートヘルスチェック
- `GET /api/health` - 詳細ヘルスチェック（DB接続確認）
- `GET /api/dashboard` - ダッシュボード統計
- `GET /api/clients` - クライアント一覧
- `GET /api/workers` - 稼働者一覧
- `GET /api/projects` - 案件一覧

**Swagger UI:** http://localhost:8000/api/docs  
**ReDoc:** http://localhost:8000/api/redoc

---

## 🎨 開発ワークフロー

### 新機能追加
1. 仕様確認: `docs/spec/DESIGN_SPEC_v0.3.md`
2. マイグレーション作成: `alembic revision -m "description"`
3. モデル追加/修正: `src/models/`
4. サービス実装: `src/services/`
5. テスト追加: `tests/`
6. テスト実行: `pytest -v`
7. 監査ログ出力確認
8. PRに仕様参照箇所を記載

### バグ修正
1. テスト追加（再現）
2. 修正実装
3. テスト実行（PASS確認）
4. 監査ログ確認

### デプロイ
1. 全テストPASS確認
2. マイグレーション適用
3. 環境変数設定
4. APIサーバー起動
5. ヘルスチェック確認

---

## 📞 ヘルプ

### ドキュメントで探す
1. **全体像**: `README.md`
2. **構築手順**: `DEPLOYMENT_GUIDE.md`
3. **完了状況**: `docs/DEPLOYMENT_COMPLETION_2026-01-27.md`
4. **ファイル一覧**: `docs/FILE_INDEX.md`
5. **仕様詳細**: `docs/spec/DESIGN_SPEC_v0.3.md`
6. **運用手順**: `RUNBOOK_MONTHLY.md`

### よくある質問
- Q: マスタデータはどこ？
  - A: `vanzai.db` 内の `clients`, `workers`, `roles` など
  
- Q: CSVはどこ？
  - A: `kintone_app/*.csv`（サンプル）、`docs/kintone/csv/*.csv`（ドキュメント用）

- Q: APIエンドポイントは？
  - A: http://localhost:8000/api/docs で確認

- Q: テストは全部通ってる？
  - A: はい、126/126 PASS（2026-01-27時点）

---

**最終更新**: 2026-01-27  
**バージョン**: v1.0（開発環境構築完了版）
