"""localhost の試験用PostgreSQL。

通常はデータベース名 vanzai_conflict だけを使う。
テストサイトの既存DBを使うときは VANZAI_CONFLICT_ALLOW_SITE_DB=1 を明示する。
接続先が 127.0.0.1 または localhost でない場合は実行しない。
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATABASE = "vanzai_conflict"
_URL_RE = re.compile(r"(postgres(?:ql)?(?:\+\w+)?://)[^\s'\"\\]+")


def _redact(value: str) -> str:
    return _URL_RE.sub(r"\1***", value or "")


def _require_local_conflict_database() -> str:
    raw = os.environ.get("VANZAI_CONFLICT_TEST_URL", "")
    if not raw:
        pytest.skip("VANZAI_CONFLICT_TEST_URL が無いため、競合試験基盤は未実行")
    url = make_url(raw)
    host = (url.host or "").lower()
    if host not in {"127.0.0.1", "localhost"}:
        pytest.fail("試験用PostgreSQLは 127.0.0.1 または localhost だけを使う")
    allow_site = os.environ.get("VANZAI_CONFLICT_ALLOW_SITE_DB") == "1"
    if url.database != LOCAL_DATABASE and not allow_site:
        pytest.fail("試験用データベース名は vanzai_conflict だけを使う")
    if not url.database:
        pytest.fail("データベース名がありません")
    return raw


@pytest.fixture(scope="session")
def conflict_engine():
    url = _require_local_conflict_database()
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if upgrade.returncode != 0 or "PostgresqlImpl" not in upgrade.stderr:
        pytest.fail(
            "試験用マイグレーションに失敗しました\n"
            f"{_redact(upgrade.stderr)}\n{_redact(upgrade.stdout)}"
        )
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()
