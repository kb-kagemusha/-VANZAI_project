"""
FastAPI メインアプリケーション（簡易版）

案件・シフト・実績・請求・支払 一元管理システムのREST API
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.api.deps import get_db

# FastAPIアプリケーション初期化
app = FastAPI(
    title="VANZAI API",
    description="案件・シフト・実績・請求・支払 一元管理システム",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================
# ヘルスチェック
# ===========================

@app.get("/", tags=["Health"])
async def root():
    """APIヘルスチェック"""
    return {"status": "ok", "message": "VANZAI API is running"}


@app.get("/api/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """詳細ヘルスチェック（DB接続確認付き）"""
    try:
        # DB接続確認
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "1.0.0",
        "services": {
            "database": db_status,
            "api": "ready"
        }
    }


# ===========================
# ダッシュボードエンドポイント
# ===========================

@app.get("/api/dashboard", tags=["Dashboard"])
async def get_dashboard(db: Session = Depends(get_db)):
    """
    ダッシュボード取得
    
    未処理項目、差異アラート、締め状況を一括取得
    """
    from src.models.master import Client, Worker
    from src.models.transaction import Project
    
    # 簡易的な統計情報を返す
    return {
        "counts": {
            "clients": db.query(Client).count(),
            "workers": db.query(Worker).count(),
            "projects": db.query(Project).count()
        },
        "unprocessed_items": [],
        "variance_alerts": [],
        "closing_status": []
    }


# ===========================
# マスタデータエンドポイント
# ===========================

@app.get("/api/clients", tags=["Master"])
async def list_clients(db: Session = Depends(get_db)):
    """クライアント一覧"""
    from src.models.master import Client
    clients = db.query(Client).filter(Client.deleted_at.is_(None)).all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "contact_email": c.contact_email
        }
        for c in clients
    ]


@app.get("/api/workers", tags=["Master"])
async def list_workers(db: Session = Depends(get_db)):
    """稼働者一覧"""
    from src.models.master import Worker
    workers = db.query(Worker).filter(Worker.deleted_at.is_(None)).all()
    return [
        {
            "id": w.id,
            "name": w.name,
            "email": w.email,
            "is_active": w.is_active
        }
        for w in workers
    ]


@app.get("/api/projects", tags=["Master"])
async def list_projects(db: Session = Depends(get_db)):
    """案件一覧"""
    from src.models.transaction import Project
    projects = db.query(Project).filter(Project.deleted_at.is_(None)).all()
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "start_date": str(p.start_date) if p.start_date else None,
            "end_date": str(p.end_date) if p.end_date else None
        }
        for p in projects
    ]
