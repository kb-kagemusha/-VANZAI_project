"""
VPS: 全アクティブワーカーの資格情報をランダム投入
- smoking_area_ok: 50% ◯
- p_shirt_count: 0/1/2枚 ランダム
- has_best: 60% ◯
- license_type: hiace_ok / at_only / none ランダム
- stores_training_done: 90% ◯
- pioneer_training_done: 90% ◯
実行: .venv/bin/python3 scripts/fill_worker_quals.py
"""
import psycopg2
import random

DB = "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod"

conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("SELECT id, name FROM workers WHERE is_active = true AND deleted_at IS NULL")
workers = cur.fetchall()

for wid, wname in workers:
    smoking = random.random() < 0.5
    p_shirt = random.choice([0, 0, 1, 1, 2])  # 0が多め
    has_best = random.random() < 0.6
    license_type = random.choices(
        ["hiace_ok", "at_only", "none"],
        weights=[30, 30, 40],
    )[0]
    stores = random.random() < 0.9
    pioneer = random.random() < 0.9

    cur.execute("""
        UPDATE workers SET
            smoking_area_ok         = %s,
            p_shirt_count           = %s,
            has_best                = %s,
            license_type            = %s,
            stores_training_done    = %s,
            pioneer_training_done   = %s,
            updated_at              = NOW()
        WHERE id = %s
    """, (smoking, p_shirt, has_best, license_type, stores, pioneer, wid))
    print(f"  {wname}: 喫煙所={smoking}, Pシャツ={p_shirt}, ベスト={has_best}, 免許={license_type}, stores={stores}, pioneer={pioneer}")

conn.commit()
print(f"\n完了: {len(workers)}名 更新")
cur.close()
conn.close()
