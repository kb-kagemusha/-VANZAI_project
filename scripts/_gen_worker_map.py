#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite workersテーブルからJS埋め込み用ULIDマップを生成"""
import sqlite3, sys
from pathlib import Path

db = Path(__file__).parent.parent / "vanzai.db"
conn = sqlite3.connect(str(db))
cur = conn.cursor()
cur.execute("SELECT id, name FROM workers WHERE deleted_at IS NULL ORDER BY id")
rows = cur.fetchall()
conn.close()

print("const WORKER_ULID_MAP = {")
for ulid, name in rows:
    safe = name.replace("\\", "\\\\").replace('"', '\\"')
    print(f'  "{ulid}": "{safe}",')
print("};")
