#!/usr/bin/env python
"""DBテーブル構造確認"""
import sys
from pathlib import Path
import sqlite3

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

db_path = project_root / "vanzai.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 複数テーブル確認
for table_name in ['expenses', 'incentives', 'invoices', 'payouts']:
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"\n=== {table_name} テーブル構造 ===")
    if columns:
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
    else:
        print("  テーブルが存在しません")

conn.close()
