import psycopg2
DB = "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod"
TAG = "%【サンプルデータ】%"
conn = psycopg2.connect(DB)
cur = conn.cursor()
for tbl in ["assignments", "shift_slots", "projects", "sites", "clients"]:
    cur.execute(f"DELETE FROM {tbl} WHERE notes LIKE %s", (TAG,))
    print(f"  deleted from {tbl}: {cur.rowcount}")
conn.commit()
print("done")
