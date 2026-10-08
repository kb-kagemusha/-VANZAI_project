"""
VPS: 全アクティブワーカーの 2026/4/1〜5/31 を 100% 埋める
既存レコードは ON CONFLICT DO NOTHING でスキップ
実行: .venv/bin/python3 scripts/fill_availability_full.py
"""
import psycopg2
import random
import uuid
from datetime import date, timedelta

DB = "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod"

# 出勤可能を多め（土日は不可比率上げる）
WEEKDAY_POOL = [
    "available_all_day", "available_all_day", "available_all_day",
    "available", "available",
    "available_after_15",
    "unavailable",
    "consult_required",
]
WEEKEND_POOL = [
    "available_all_day", "available",
    "available_after_15",
    "unavailable", "unavailable",
    "consult_required",
]

def gen_ulid():
    return uuid.uuid4().hex[:26]

conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("SELECT id, name FROM workers WHERE is_active = true AND deleted_at IS NULL")
workers = cur.fetchall()

start = date(2026, 4, 1)
end   = date(2026, 5, 31)
days = []
d = start
while d <= end:
    days.append(d)
    d += timedelta(days=1)

inserted = 0
for wid, wname in workers:
    for day in days:
        pool = WEEKEND_POOL if day.weekday() >= 5 else WEEKDAY_POOL
        status = random.choice(pool)
        cur.execute("""
            INSERT INTO worker_availability (id, worker_id, availability_date, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (worker_id, availability_date) DO NOTHING
        """, (gen_ulid(), wid, day, status))
        inserted += cur.rowcount
    conn.commit()

print(f"完了: {len(workers)}名 × {len(days)}日 → {inserted}件 新規追加（既存スキップ）")
cur.close()
conn.close()
