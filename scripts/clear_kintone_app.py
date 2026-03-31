"""
Kintoneアプリのデータ全削除

警告: このスクリプトは指定したKintoneアプリの全レコードを削除します

使用方法:
    python scripts/clear_kintone_app.py [アプリID]
    
    例: python scripts/clear_kintone_app.py 165
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import requests

load_dotenv()

app_id = int(sys.argv[1]) if len(sys.argv) > 1 else None

if not app_id:
    print("使用方法: python scripts/clear_kintone_app.py [アプリID]")
    sys.exit(1)

# アプリ名とトークンのマッピング
app_info = {
    165: {"name": "workers", "token_env": "KINTONE_TOKEN_WORKERS"},
    167: {"name": "clients", "token_env": "KINTONE_TOKEN_CLIENTS"},
    166: {"name": "sites", "token_env": "KINTONE_TOKEN_SITES"},
    163: {"name": "roles", "token_env": "KINTONE_TOKEN_ROLES"},
    164: {"name": "project_types", "token_env": "KINTONE_TOKEN_PROJECT_TYPES"},
}

subdomain = os.getenv("KINTONE_SUBDOMAIN")
guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
info = app_info.get(app_id, {})
token_env = info.get("token_env")
if not token_env:
    print("❌ エラー: このアプリIDはトークン環境変数のマッピングがありません")
    print("app_info に token_env を追加してください")
    sys.exit(1)

token = os.getenv(token_env)

if not token:
    print(f"❌ エラー: APIトークンが設定されていません（{token_env}）")
    sys.exit(1)

# URL
if guest_space_id:
    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
else:
    base_url = f"https://{subdomain}.cybozu.com/k/v1"

headers = {
    "X-Cybozu-API-Token": token,
    "Content-Type": "application/json"
}

# GET用ヘッダー（Content-Type不要）
get_headers = {
    "X-Cybozu-API-Token": token
}

print(f"=" * 60)
print(f"Kintoneアプリデータ全削除")
print(f"=" * 60)
print(f"アプリID: {app_id}")
print(f"アプリ名: {info.get('name', 'unknown')}")

# レコード取得
get_url = f"{base_url}/records.json"
response = requests.get(get_url, headers=get_headers, params={"app": str(app_id)}, timeout=30)

if response.status_code != 200:
    print(f"❌ エラー: {response.status_code}")
    print(f"レスポンス: {response.text}")
    sys.exit(1)

data = response.json()
records = data.get("records", [])

if not records:
    print(f"✅ レコードは既に0件です")
    sys.exit(0)

print(f"現在のレコード数: {len(records)}")

# 確認
print(f"\n⚠️ 警告: {len(records)}件のレコードを削除します")
print(f"実行してよろしいですか？ [y/n]: ", end="")
confirmation = input().strip().lower()

if confirmation != 'y':
    print("❌ キャンセルしました")
    sys.exit(0)

# 削除実行
record_ids = [record["$id"]["value"] for record in records]

# 100件ずつ削除（Kintone APIの制限）
delete_url = f"{base_url}/records.json"
batch_size = 100
total_deleted = 0

for i in range(0, len(record_ids), batch_size):
    batch_ids = record_ids[i:i + batch_size]
    
    payload = {
        "app": app_id,
        "ids": batch_ids
    }
    
    try:
        response = requests.delete(delete_url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            total_deleted += len(batch_ids)
            print(f"✅ 削除進捗: {total_deleted}/{len(record_ids)}")
        else:
            print(f"❌ エラー: {response.status_code}")
            print(f"レスポンス: {response.text}")
            break
    except Exception as e:
        print(f"❌ エラー: {e}")
        break

if total_deleted == len(record_ids):
    print(f"\n✅ 削除完了: {total_deleted}件")
else:
    print(f"\n⚠️ 一部削除失敗: {total_deleted}/{len(record_ids)}")
