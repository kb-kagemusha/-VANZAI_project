"""
依存性注入（Dependency Injection）

FastAPIのDependsで使用する共通依存関係を定義
"""
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _create_engine(database_url: str):
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


# データベース接続設定
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vanzai.db")
engine = _create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    データベースセッション依存関係
    
    各リクエストで新しいセッションを作成し、処理後に自動的にクローズする
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
