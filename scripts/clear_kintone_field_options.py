"""
Kintoneドロップダウン/ラジオボタンの選択肢を空にする

選択肢制限を削除して自由入力可能にします

使用方法:
    python scripts/clear_kintone_field_options.py [アプリID]
    
    例: python scripts/clear_kintone_field_options.py 165
"""
import os
import sys
from pathlib import Path
import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

app_id = int(sys.argv[1]) if len(sys.argv) > 1 else 165

# アプリ設定
APP_CONFIGS = {
    165: {
        "name": "workers",
        "token_env": "KINTONE_TOKEN_WORKERS",
        "fields_to_clear": ["worker_id", "name", "phone"]  # is_activeは残す
    },
    167: {
        "name": "clients",
        "token_env": "KINTONE_TOKEN_CLIENTS",
        "fields_to_clear": ["client_id", "name", "code", "address"]
    },
    166: {
        "name": "sites",
        "token_env": "KINTONE_TOKEN_SITES",
        "fields_to_clear": ["site_id", "name", "code", "address"]
    },
    163: {
        "name": "roles",
        "token_env": "KINTONE_TOKEN_ROLES",
        "fields_to_clear": ["role_id", "name", "description"]
    },
    164: {
        "name": "project_types",
        "token_env": "KINTONE_TOKEN_PROJECT_TYPES",
        "fields_to_clear": ["type_id", "name", "description"]
    }
}

print(f"=" * 60)
print(f"Kintoneフィールド選択肢削除")
print(f"=" * 60)
print(f"アプリID: {app_id}")

config = APP_CONFIGS.get(app_id)
if not config:
    print(f"❌ エラー: アプリID {app_id} の設定がありません")
    sys.exit(1)

subdomain = os.getenv("KINTONE_SUBDOMAIN")
guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
token = os.getenv(config["token_env"])

if not token:
    print(f"❌ エラー: APIトークンが設定されていません")
    sys.exit(1)

print(f"アプリ名: {config['name']}")

# ヘッダー
get_headers = {"X-Cybozu-API-Token": token}
headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}

# URL
if guest_space_id:
    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
else:
    base_url = f"https://{subdomain}.cybozu.com/k/v1"

# ステップ1: 現在のフィールド定義を取得
print(f"\n[ステップ1] 現在のフィールド定義を取得中...")

get_url = f"{base_url}/app/form/fields.json"
response = requests.get(get_url, headers=get_headers, params={"app": str(app_id)}, timeout=30)

if response.status_code != 200:
    print(f"❌ エラー: {response.status_code}")
    print(f"レスポンス: {response.text}")
    sys.exit(1)

data = response.json()
properties = data.get("properties", {})

print(f"✅ 取得成功: {len(properties)} フィールド")

# ステップ2: 選択肢を空にするフィールドを特定
print(f"\n[ステップ2] 選択肢を削除するフィールドを特定中...")

update_properties = {}
changes = []

for field_code, field_props in properties.items():
    field_type = field_props.get("type")
    label = field_props.get("label", "")
    
    # 対象フィールドかチェック
    if field_code not in config["fields_to_clear"]:
        continue
    
    # ドロップダウンまたはラジオボタンのみ
    if field_type not in ("DROP_DOWN", "RADIO_BUTTON"):
        print(f"  ⚠️ スキップ: {field_code} ({field_type}) - 対象外のタイプ")
        continue
    
    # 選択肢があるかチェック
    options = field_props.get("options", {})
    if not options:
        print(f"  ⚠️ スキップ: {field_code} - 既に選択肢なし")
        continue
    
    # 選択肢を最小限にする設定（空は不可なのでダミーを1つ）
    update_prop = {
        "type": field_type,
        "code": field_code,
        "label": label,
        "options": {
            "__dummy__": {"label": "__dummy__", "index": "0"}  # ダミー選択肢
        }
    }
    
    if field_type == "RADIO_BUTTON":
        update_prop["defaultValue"] = "__dummy__"
    
    update_properties[field_code] = update_prop
    
    change = f"  {field_code:20s} ({field_type:15s}) - 選択肢 {len(options)} 個を削除"
    changes.append(change)
    print(change)

if not changes:
    print("✅ 削除が必要な選択肢はありません")
    sys.exit(0)

# 確認
auto_yes = "--yes" in sys.argv or "-y" in sys.argv

print(f"\n" + "=" * 60)
print(f"⚠️ 警告: フィールドの選択肢を削除します")
print(f"=" * 60)
print(f"アプリID: {app_id} ({config['name']})")
print(f"変更数: {len(changes)} フィールド")

if not auto_yes:
    print(f"\n実行してよろしいですか？ [y/n]: ", end="")
    confirmation = input().strip().lower()
    if confirmation != 'y':
        print("\n❌ キャンセルしました")
        sys.exit(0)
else:
    print("\n自動実行モード（--yes指定）")

# ステップ3: 選択肢を削除（プレビュー）
print(f"\n[ステップ3] 選択肢を削除中（プレビュー）...")

put_url = f"{base_url}/preview/app/form/fields.json"
payload = {"app": app_id, "properties": update_properties}

try:
    response = requests.put(put_url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        print(f"✅ プレビュー更新成功")
        
        # ステップ4: アプリを公開
        print(f"\n[ステップ4] アプリを公開（プレビュー→本番）...")
        
        deploy_url = f"{base_url}/preview/app/deploy.json"
        deploy_payload = {"apps": [{"app": app_id}]}
        
        response = requests.post(deploy_url, headers=headers, json=deploy_payload, timeout=60)
        
        if response.status_code == 200:
            print(f"✅ アプリ公開成功")
            
            print(f"\n" + "=" * 60)
            print(f"✅ 完了しました")
            print(f"=" * 60)
            
            print(f"\n削除された選択肢:")
            for change in changes:
                print(change)
            
            print(f"\n次のステップ:")
            print(f"1. Kintoneでアプリを開いて確認")
            print(f"2. データ同期を実行:")
            print(f"   python scripts/sync_db_to_kintone.py {config['name']}")
        else:
            print(f"❌ アプリ公開エラー: {response.status_code}")
            print(f"レスポンス: {response.text}")
            sys.exit(1)
    else:
        print(f"❌ フィールド更新エラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        
        if response.status_code == 403:
            print(f"\n💡 ヒント: APIトークンに「アプリの設定」権限が必要です")
        
        sys.exit(1)

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
