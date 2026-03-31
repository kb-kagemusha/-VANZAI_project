#!/usr/bin/env python
"""DBの各テーブルの件数を確認するスクリプト"""
import sqlite3
import sys

def check_counts(db_path='vanzai.db'):
    tables = ['workers', 'clients', 'sites', 'roles', 'project_types', 
              'projects', 'actuals', 'assignments', 'shift_slots', 'expenses', 'incentives']
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n=== データベーステーブル件数 ===")
    for table in tables:
        try:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table:20s}: {count:5d} 件")
        except sqlite3.OperationalError as e:
            print(f"{table:20s}: テーブルなし")
    
    conn.close()
    print()

if __name__ == '__main__':
    check_counts()
