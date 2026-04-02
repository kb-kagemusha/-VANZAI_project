"""
VPS: サンプル案件・シフト枠・配置データ投入
識別子(notes): 【サンプルデータ】
削除方法:
  DELETE FROM assignments   WHERE notes LIKE '%【サンプルデータ】%';
  DELETE FROM shift_slots   WHERE notes LIKE '%【サンプルデータ】%';
  DELETE FROM projects      WHERE notes LIKE '%【サンプルデータ】%';
  DELETE FROM sites         WHERE notes LIKE '%【サンプルデータ】%';
  DELETE FROM clients       WHERE notes LIKE '%【サンプルデータ】%';
実行: python add_sample_projects.py
"""
import os
import uuid
import random
from datetime import date, timedelta, time

import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod",
)
SAMPLE_TAG = "【サンプルデータ】"

def gen_ulid():
    return uuid.uuid4().hex[:26]

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # ─── 既存サンプルデータ確認 ─────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM projects WHERE notes LIKE %s", (f"%{SAMPLE_TAG}%",))
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"サンプル案件が既に {existing} 件存在します。スキップします。")
        print("削除して再実行したい場合は add_sample_projects.py 内のコメントを参照してください。")
        cur.close()
        conn.close()
        return

    # ─── 1. サンプルクライアント ─────────────────────────────────────────
    clients_data = [
        ("株式会社サンプル商事", "SMP-001"),
        ("サンプルロジスティクス株式会社", "SMP-002"),
    ]
    client_ids = []
    for cname, ccode in clients_data:
        cur.execute("SELECT id FROM clients WHERE code = %s", (ccode,))
        row = cur.fetchone()
        if row:
            client_ids.append(row[0])
        else:
            cid = gen_ulid()
            cur.execute(
                """
                INSERT INTO clients (id, name, code, notes, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                (cid, cname, ccode, SAMPLE_TAG),
            )
            client_ids.append(cid)
            print(f"  [client] {cname}")
    conn.commit()

    # ─── 2. サンプル現場 ─────────────────────────────────────────────────
    sites_data = [
        ("東京サンプル倉庫", "SITE-SMP-001"),
        ("大阪サンプルセンター", "SITE-SMP-002"),
        ("横浜サンプルターミナル", "SITE-SMP-003"),
    ]
    site_ids = []
    for sname, scode in sites_data:
        cur.execute("SELECT id FROM sites WHERE code = %s", (scode,))
        row = cur.fetchone()
        if row:
            site_ids.append(row[0])
        else:
            sid = gen_ulid()
            cur.execute(
                """
                INSERT INTO sites (id, name, code, notes, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                (sid, sname, scode, SAMPLE_TAG),
            )
            site_ids.append(sid)
            print(f"  [site] {sname}")
    conn.commit()

    # ─── 3. ロール取得（既存を流用、なければ作成）──────────────────────
    cur.execute("SELECT id, name FROM roles WHERE deleted_at IS NULL LIMIT 3")
    roles = cur.fetchall()
    if not roles:
        role_id = gen_ulid()
        cur.execute(
            """
            INSERT INTO roles (id, name, code, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            """,
            (role_id, "スタッフ", "STAFF"),
        )
        conn.commit()
        cur.execute("SELECT id, name FROM roles WHERE deleted_at IS NULL LIMIT 3")
        roles = cur.fetchall()
    print(f"  使用ロール: {[r[1] for r in roles]}")

    # ─── 4. アクティブワーカー取得 ────────────────────────────────────────
    cur.execute("SELECT id, name FROM workers WHERE is_active = true AND deleted_at IS NULL ORDER BY created_at LIMIT 20")
    workers = cur.fetchall()
    if not workers:
        print("アクティブなワーカーがいません")
        return
    print(f"  配置対象ワーカー: {len(workers)}名")

    # ─── 5. サンプル案件・シフト枠・配置 ────────────────────────────────
    projects = [
        {
            "name": "サンプル案件A（イベント設営）",
            "code": "PROJ-SMP-001",
            "client_id": client_ids[0],
            "site_id": site_ids[0],
            "start_date": date(2026, 4, 7),
            "end_date": date(2026, 4, 30),
            "shifts_per_day": [  # (shift_label, start_time, end_time, required)
                ("日勤", time(9, 0), time(18, 0), 3),
                ("夜勤", time(18, 0), time(23, 0), 2),
            ],
        },
        {
            "name": "サンプル案件B（倉庫ピッキング）",
            "code": "PROJ-SMP-002",
            "client_id": client_ids[1],
            "site_id": site_ids[1],
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 5, 31),
            "shifts_per_day": [
                ("午前", time(8, 0), time(13, 0), 4),
                ("午後", time(13, 0), time(18, 0), 4),
            ],
        },
        {
            "name": "サンプル案件C（運搬補助）",
            "code": "PROJ-SMP-003",
            "client_id": client_ids[0],
            "site_id": site_ids[2],
            "start_date": date(2026, 4, 14),
            "end_date": date(2026, 5, 10),
            "shifts_per_day": [
                ("全日", time(10, 0), time(17, 0), 2),
            ],
        },
    ]

    total_slots = 0
    total_assigns = 0

    for proj_data in projects:
        pid = gen_ulid()
        cur.execute(
            """
            INSERT INTO projects
              (id, name, code, client_id, site_id, start_date, end_date, notes,
               is_active, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s, true, NOW(), NOW())
            """,
            (
                pid,
                proj_data["name"],
                proj_data["code"],
                proj_data["client_id"],
                proj_data["site_id"],
                proj_data["start_date"],
                proj_data["end_date"],
                SAMPLE_TAG,
            ),
        )
        print(f"  [project] {proj_data['name']}")

        # シフト枠: 開始日〜終了日、平日のみ
        d = proj_data["start_date"]
        while d <= proj_data["end_date"]:
            if d.weekday() < 5:  # 月〜金
                for shift_label, start_t, end_t, required in proj_data["shifts_per_day"]:
                    slot_id = gen_ulid()
                    cur.execute(
                        """
                        INSERT INTO shift_slots
                          (id, project_id, work_date, start_time, end_time,
                           shift_label, required_count, notes, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s, NOW(), NOW())
                        """,
                        (
                            slot_id, pid, d, start_t, end_t,
                            shift_label, required, SAMPLE_TAG,
                        ),
                    )
                    total_slots += 1

                    # 各シフト枠にランダムにワーカーを配置（required_count 人）
                    chosen = random.sample(workers, min(required, len(workers)))
                    role = random.choice(roles)
                    for w_id, w_name in chosen:
                        assign_id = gen_ulid()
                        status = random.choice(["tentative", "confirmed"])
                        cur.execute(
                            """
                            INSERT INTO assignments
                              (id, shift_slot_id, worker_id, role_id, status,
                               worker_response_status, worker_response_requested_at,
                               notes, created_at, updated_at)
                            VALUES (%s,%s,%s,%s,%s,'pending', NOW(), %s, NOW(), NOW())
                            """,
                            (assign_id, slot_id, w_id, role[0], status, SAMPLE_TAG),
                        )
                        total_assigns += 1
            d += timedelta(days=1)

        conn.commit()

    print(f"\n完了: 案件{len(projects)}件, シフト枠{total_slots}件, 配置{total_assigns}件 投入")
    print(f"削除コマンド (SAMPLE_TAG='{SAMPLE_TAG}'):")
    print(f"  DELETE FROM assignments WHERE notes LIKE '%{SAMPLE_TAG}%';")
    print(f"  DELETE FROM shift_slots  WHERE notes LIKE '%{SAMPLE_TAG}%';")
    print(f"  DELETE FROM projects     WHERE notes LIKE '%{SAMPLE_TAG}%';")
    print(f"  DELETE FROM sites        WHERE notes LIKE '%{SAMPLE_TAG}%';")
    print(f"  DELETE FROM clients      WHERE notes LIKE '%{SAMPLE_TAG}%';")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
