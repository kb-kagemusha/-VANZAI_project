"""版管理列の拡張は PostgreSQL だけが行う。"""
from sqlalchemy import create_engine

from src.alembic_support import widen_existing_version_num


def test_version_widen_skips_sqlite():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        widen_existing_version_num(connection)
