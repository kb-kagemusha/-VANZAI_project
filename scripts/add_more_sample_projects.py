"""
VPS: 追加サンプル案件投入（4月1日始まり含む）
既存サンプル案件はそのまま保持して追記
実行: .venv/bin/python3 scripts/add_more_sample_projects.py
"""
import os
import uuid
import random
from datetime import date, timedelta, time

import psycopg2

DB = "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod"
SAMPLE_TAG = "【サンプルデータ】"

def gen_ulid():
    return uuid.uuid4().hex[:26]

NEW_PROJECTS = [
    {
        "name": "サンプル案件D（開梱・検品）",
        "code": "PROJ-SMP-004",
        "client_code": "SMP-001",
        "site_code": "SITE-SMP-001",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 5, 31),
        "shifts": [
            ("日勤", time(9, 0), time(18, 0), 3),
        ],
    },
    {
        "name": "サンプル案件E（展示会準備）",
        "code": "PROJ-SMP-005",
        "client_code": "SMP-002",
        "site_code": "SITE-SMP-003",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 4, 12),
        "shifts": [
            ("早番", time(7, 0), time(14, 0), 2),
            ("遅番", time(14, 0), time(21, 0), 2),
        ],
    },
    {
        "name": "サンプル案件F（GW特別対応）",
        "code": "PROJ-SMP-006",
        "client_code": "SMP-001",
        "site_code": "SITE-SMP-002",
        "start_date": date(2026, 4, 28),
        "end_date": date(2026, 5, 6),
        "shifts": [
            ("全日", time(10, 0), time(19, 0), 5),
        ],
    },
    {
        "name": "サンプル案件G（定期清掃業務）",
        "code": "PROJ-SMP-007",
        "client_code": "SMP-002",
        "site_code": "SITE-SMP-001",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 5, 31),
        "shifts": [
            ("午前", time(8, 0), time(12, 0), 2),
        ],
    },
    {
        "name": "サンプル案件H（商品仕分け）",
        "code": "PROJ-SMP-008",
        "client_code": "SMP-001",
        "site_code": "SITE-SMP-003",
        "start_date": date(2026, 4, 7),
        "end_date": date(2026, 5, 16),
        "shifts": [
            ("日勤", time(9, 0), time(18, 0), 4),
            ("夜勤", time(20, 0), time(6, 0), 2),
        ],
    },
]

def main():
    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    # クライアント・現場のIDをコードで取得
    def get_id(table, code_col, code):
        cur.execute(f"SELECT id FROM {table} WHERE {code_col} = %s", (code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"{table} code={code} not found")
        return row[0]

    # ロール取得
    cur.execute("SELECT id FROM roles WHERE deleted_at IS NULL LIMIT 1")
    role_row = cur.fetchone()
    if not role_row:
        raise ValueError("ロールが存在しません")
    role_id = role_row[0]

    # アクティブワーカー
    cur.execute("SELECT id FROM workers WHERE is_active = true AND deleted_at IS NULL")
    workers = [r[0] for r in cur.fetchall()]

    total_slots = 0
    total_assigns = 0

    for pd in NEW_PROJECTS:
        # 既存チェック
        cur.execute("SELECT id FROM projects WHERE code = %s", (pd["code"],))
        if cur.fetchone():
            print(f"  [skip] {pd['name']} 既存")
            continue

        cid = get_id("clients", "code", pd["client_code"])
        sid = get_id("sites",   "code", pd["site_code"])

        pid = gen_ulid()
        cur.execute("""
            INSERT INTO projects
              (id, name, code, client_id, site_id, start_date, end_date, notes,
               is_active, rounding_unit_minutes, rounding_method, break_deduction_rule,
               time_calc_mode, night_calc_mode, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s, true,
                    15,'ceil','auto','system_first','store_minutes', NOW(), NOW())
        """, (pid, pd["name"], pd["code"], cid, sid,
              pd["start_date"], pd["end_date"], SAMPLE_TAG))
        print(f"  [add] {pd['name']}")

        d = pd["start_date"]
        while d <= pd["end_date"]:
            # GW案件は土日も含む、それ以外は平日のみ
            is_gw = pd["code"] == "PROJ-SMP-006"
            if is_gw or d.weekday() < 5:
                for shift_label, start_t, end_t, required in pd["shifts"]:
                    slot_id = gen_ulid()
                    cur.execute("""
                        INSERT INTO shift_slots
                          (id, project_id, work_date, start_time, end_time,
                           shift_label, required_count, notes, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s, NOW(), NOW())
                    """, (slot_id, pid, d, start_t, end_t, shift_label, required, SAMPLE_TAG))
                    total_slots += 1

                    chosen = random.sample(workers, min(required, len(workers)))
                    for w_id in chosen:
                        cur.execute("""
                            INSERT INTO assignments
                              (id, shift_slot_id, worker_id, role_id, status,
                               worker_response_status, worker_response_requested_at,
                               notes, created_at, updated_at)
                            VALUES (%s,%s,%s,%s,%s,'pending', NOW(),%s, NOW(), NOW())
                        """, (gen_ulid(), slot_id, w_id, role_id,
                              random.choice(["tentative", "confirmed"]), SAMPLE_TAG))
                        total_assigns += 1
            d += timedelta(days=1)

        conn.commit()

    print(f"\n完了: シフト枠 {total_slots}件, 配置 {total_assigns}件 追加")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
