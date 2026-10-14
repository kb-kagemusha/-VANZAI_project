"""
VPS: 日本語名ワーカー6名追加＋全ワーカーの4〜5月ランダム予定投入
実行: python add_jp_workers_and_availability.py
"""
import os
import random
import uuid
from datetime import date, timedelta

import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod",
)

def gen_ulid():
    # 簡易 ULID 代替: UUID4 の hex を 26 文字に収める
    return uuid.uuid4().hex[:26]

NEW_WORKERS = [
    ("山田 太郎", "yamada.taro@vanzai-sample.jp", "090-3100-0001"),
    ("田中 花子", "tanaka.hanako@vanzai-sample.jp", "090-3100-0002"),
    ("鈴木 一郎", "suzuki.ichiro@vanzai-sample.jp", "090-3100-0003"),
    ("佐藤 美咲", "sato.misaki@vanzai-sample.jp", "090-3100-0004"),
    ("高橋 健二", "takahashi.kenji@vanzai-sample.jp", "090-3100-0005"),
    ("伊藤 直子", "ito.naoko@vanzai-sample.jp", "090-3100-0006"),
]

AVAIL_STATUSES = [
    "available_all_day",
    "available_all_day",  # 出勤可を多めに
    "available",
    "available_after_15",
    "unavailable",
    "consult_required",
]

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # ─── 1. 新規ワーカー挿入（重複はスキップ） ─────────────────────────
    new_worker_ids = []
    for name, email, phone in NEW_WORKERS:
        cur.execute("SELECT id FROM workers WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            print(f"  [skip] {name} ({email}) 既存")
            new_worker_ids.append(row[0])
        else:
            wid = gen_ulid()
            cur.execute(
                """
                INSERT INTO workers (id, name, email, phone, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, true, NOW(), NOW())
                """,
                (wid, name, email, phone),
            )
            print(f"  [add]  {name} (id={wid})")
            new_worker_ids.append(wid)

    conn.commit()

    # ─── 2. 全アクティブワーカーに 4〜5月の予定を投入（重複はスキップ） ─
    cur.execute("SELECT id, name FROM workers WHERE is_active = true AND deleted_at IS NULL")
    all_workers = cur.fetchall()

    start_date = date(2026, 4, 1)
    end_date = date(2026, 5, 31)
    days = []
    d = start_date
    while d <= end_date:
        days.append(d)
        d += timedelta(days=1)

    inserted = 0
    skipped = 0
    for wid, wname in all_workers:
        for day in days:
            # 15% の確率でその日をスキップ（未登録のまま）
            if random.random() < 0.15:
                skipped += 1
                continue
            status = random.choice(AVAIL_STATUSES)
            aid = gen_ulid()
            try:
                cur.execute(
                    """
                    INSERT INTO worker_availability (id, worker_id, availability_date, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (worker_id, availability_date) DO NOTHING
                    """,
                    (aid, wid, day, status),
                )
                inserted += cur.rowcount
            except Exception as e:
                print(f"  [err] worker={wname} date={day}: {e}")
                conn.rollback()
                break
        conn.commit()

    print(f"\n完了: ワーカー {len(NEW_WORKERS)}名追加, 予定 {inserted}件投入, {skipped}件スキップ")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
