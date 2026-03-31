import sqlite3
conn = sqlite3.connect('vanzai.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print('tables:', tables)

# workers テーブルがあればULID→名前を確認
if 'workers' in tables:
    cur.execute('PRAGMA table_info(workers)')
    cols = [r[1] for r in cur.fetchall()]
    print('workers cols:', cols)
    cur.execute('SELECT * FROM workers LIMIT 5')
    for row in cur.fetchall(): print(' ', row)
elif 'worker' in tables:
    cur.execute("PRAGMA table_info(worker)")
    cols = [r[1] for r in cur.fetchall()]
    print('worker cols:', cols)
    cur.execute("SELECT * FROM worker LIMIT 5")
    for row in cur.fetchall(): print(' ', row)
conn.close()
