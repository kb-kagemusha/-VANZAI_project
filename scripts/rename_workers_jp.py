"""
VPS: 英語名ワーカーを日本語名に変更
実行: .venv/bin/python3 scripts/rename_workers_jp.py
"""
import psycopg2

DB = "postgresql://vanzai_db:XC2YdeMLbNpvqgdooP9HJ0cF@localhost:5432/vanzai_prod"

RENAMES = {
    "Aki Tanaka":       "田中 亜紀",
    "Hiro Sato":        "佐藤 裕",
    "Mina Suzuki":      "鈴木 美奈",
    "Ken Yamamoto":     "山本 健",
    "Yui Kobayashi":    "小林 由衣",
    "Sora Ito":         "伊東 空",
    "Rina Nakamura":    "中村 里奈",
    "Daichi Watanabe":  "渡辺 大地",
    "Nao Kato":         "加藤 奈央",
    "Koki Fujita":      "藤田 浩樹",
    "Browser Smoke Mobile Worker": "テスト アカウント",
}

conn = psycopg2.connect(DB)
cur = conn.cursor()
for old, new in RENAMES.items():
    cur.execute("UPDATE workers SET name = %s, updated_at = NOW() WHERE name = %s", (new, old))
    print(f"  {old} → {new} ({cur.rowcount}件)")
conn.commit()
print("完了")
cur.close()
conn.close()
