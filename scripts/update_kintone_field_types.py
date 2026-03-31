"""
Kintoneアプリのフィールドタイプとコードを一括変更

ドロップダウン/ラジオボタン → 文字列（1行/複数行）に変更し、
フィールドコードも英語に統一します

使用方法:
    python scripts/update_kintone_field_types.py [アプリID]
    
    例: python scripts/update_kintone_field_types.py 165
    
前提条件:
    - APIトークンに「アプリの設定」権限が必要
"""
import os
import sys
from pathlib import Path
import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# コマンドライン引数
app_id = int(sys.argv[1]) if len(sys.argv) > 1 else 165

# アプリ設定
APP_CONFIGS = {
    165: {  # workers
        "name": "workers",
        "token_env": "KINTONE_TOKEN_WORKERS",
        "fields": {
            "ドロップダウン": {
                "type": "DROP_DOWN",  # タイプは変更しない
                "code": "worker_id",
                "label": "worker_id",
                "options": {}  # 空にして選択肢なしに
            },
            "ドロップダウン_0": {
                "type": "DROP_DOWN",
                "code": "name",
                "label": "name",
                "options": {}
            },
            "ドロップダウン_1": {
                "type": "DROP_DOWN",
                "code": "phone",
                "label": "phone",
                "options": {}
            },
            "リンク": {
                "type": "LINK",
                "code": "email",
                "label": "email",
                "protocol": "MAIL"
            },
            "ラジオボタン": {
                "type": "RADIO_BUTTON",
                "code": "is_active",
                "label": "is_active",
                "options": {
                    "有効": {"label": "有効", "index": "0"},
                    "無効": {"label": "無効", "index": "1"}
                },
                "defaultValue": "有効"
            },
            "文字列__1行_": {
                "type": "SINGLE_LINE_TEXT",
                "code": "notes",
                "label": "notes"
            }
        }
    },
    167: {  # clients
        "name": "clients",
        "token_env": "KINTONE_TOKEN_CLIENTS",
        "fields": {
            "ラジオボタン": {
                "type": "RADIO_BUTTON",
                "code": "client_id",
                "label": "client_id",
                "options": {}
            },
            "ラジオボタン_0": {
                "type": "RADIO_BUTTON",
                "code": "name",
                "label": "name",
                "options": {}
            },
            "ラジオボタン_1": {
                "type": "RADIO_BUTTON",
                "code": "code",
                "label": "code",
                "options": {}
            },
            "ラジオボタン_2": {
                "type": "RADIO_BUTTON",
                "code": "address",
                "label": "address",
                "options": {}
            },
            "リンク": {
                "type": "LINK",
                "code": "billing_email",
                "label": "billing_email",
                "protocol": "MAIL"
            },
            "文字列__1行_": {
                "type": "SINGLE_LINE_TEXT",
                "code": "notes",
                "label": "notes"
            }
        }
    },
    166: {  # sites
        "name": "sites",
        "token_env": "KINTONE_TOKEN_SITES",
        "fields": {
            "ドロップダウン": {
                "type": "DROP_DOWN",
                "code": "site_id",
                "label": "site_id",
                "options": {}
            },
            "ドロップダウン_0": {
                "type": "DROP_DOWN",
                "code": "name",
                "label": "name",
                "options": {}
            },
            "ドロップダウン_1": {
                "type": "DROP_DOWN",
                "code": "code",
                "label": "code",
                "options": {}
            },
            "ドロップダウン_2": {
                "type": "DROP_DOWN",
                "code": "address",
                "label": "address",
                "options": {}
            },
            "文字列__1行_": {
                "type": "SINGLE_LINE_TEXT",
                "code": "notes",
                "label": "notes"
            }
        }
    },
    163: {  # roles
        "name": "roles",
        "token_env": "KINTONE_TOKEN_ROLES",
        "fields": {
            "ラジオボタン": {
                "type": "RADIO_BUTTON",
                "code": "role_id",
                "label": "role_id",
                "options": {}
            },
            "ラジオボタン_0": {
                "type": "RADIO_BUTTON",
                "code": "name",
                "label": "name",
                "options": {}
            },
            "ラジオボタン_1": {
                "type": "RADIO_BUTTON",
                "code": "description",
                "label": "description",
                "options": {}
            }
        }
    },
    164: {  # project_types
        "name": "project_types",
        "token_env": "KINTONE_TOKEN_PROJECT_TYPES",
        "fields": {
            "ラジオボタン": {
                "type": "RADIO_BUTTON",
                "code": "type_id",
                "label": "type_id",
                "options": {}
            },
            "ラジオボタン_0": {
                "type": "RADIO_BUTTON",
                "code": "name",
                "label": "name",
                "options": {}
            },
            "ラジオボタン_1": {
                "type": "RADIO_BUTTON",
                "code": "description",
                "label": "description",
                "options": {}
            }
        }
    }
}

print(f"=" * 60)
print(f"Kintoneフィールドタイプ・コード一括変更")
print(f"=" * 60)
print(f"アプリID: {app_id}")

# 設定取得
subdomain = os.getenv("KINTONE_SUBDOMAIN")
guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
config = APP_CONFIGS.get(app_id)

if not config:
    print(f"❌ エラー: アプリID {app_id} の設定がありません")
    print(f"対応アプリ: {list(APP_CONFIGS.keys())}")
    sys.exit(1)

token = os.getenv(config["token_env"])

if not token:
    print(f"❌ エラー: APIトークンが設定されていません ({config['token_env']})")
    sys.exit(1)

print(f"アプリ名: {config['name']}")

# ヘッダー
get_headers = {
    "X-Cybozu-API-Token": token
}

headers = {
    "X-Cybozu-API-Token": token,
    "Content-Type": "application/json"
}

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

# ステップ2: 変更内容を表示
print(f"\n[ステップ2] 変更内容:")

update_properties = {}
changes = []

for old_code, new_props in config["fields"].items():
    if old_code not in properties:
        print(f"  ⚠️ スキップ: {old_code} (フィールドが存在しません)")
        continue
    
    old_props = properties[old_code]
    old_type = old_props.get("type")
    new_type = new_props["type"]
    new_code = new_props["code"]
    
    # 変更内容を構築
    update_prop = {
        "type": new_type,
        "code": new_code,
        "label": new_props.get("label", new_code)
    }
    
    # フィールドタイプ固有の設定
    if new_type == "LINK":
        update_prop["protocol"] = new_props.get("protocol", "WEB")
    elif new_type == "RADIO_BUTTON" and "options" in new_props:
        options = new_props.get("options", {})
        if options:  # 選択肢が指定されている場合のみ設定
            update_prop["options"] = options
            if "defaultValue" in new_props:
                update_prop["defaultValue"] = new_props["defaultValue"]
    elif new_type == "DROP_DOWN" and "options" in new_props:
        options = new_props.get("options", {})
        if options:  # 選択肢が指定されている場合のみ設定
            update_prop["options"] = options
    elif new_type == "SINGLE_LINE_TEXT":
        update_prop["maxLength"] = new_props.get("maxLength", 200)
    elif new_type == "MULTI_LINE_TEXT":
        update_prop["maxLength"] = new_props.get("maxLength", 1000)
    
    update_properties[old_code] = update_prop
    
    change = f"  {old_code:20s} ({old_type:15s}) → {new_code:20s} ({new_type:15s})"
    changes.append(change)
    print(change)

if not changes:
    print("✅ 変更が必要なフィールドはありません")
    sys.exit(0)

# 確認
print(f"\n" + "=" * 60)
print(f"⚠️ 警告: フィールドタイプとコードを変更します")
print(f"=" * 60)
print(f"アプリID: {app_id} ({config['name']})")
print(f"変更数: {len(changes)} フィールド")
print(f"\n実行してよろしいですか？ [y/n]: ", end="")

confirmation = input().strip().lower()

if confirmation != 'y':
    print("\n❌ キャンセルしました")
    sys.exit(0)

# ステップ3: フィールド設定を更新（プレビュー）
print(f"\n[ステップ3] フィールド設定を更新中（プレビュー）...")

put_url = f"{base_url}/preview/app/form/fields.json"

payload = {
    "app": app_id,
    "properties": update_properties
}

try:
    response = requests.put(put_url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        print(f"✅ プレビュー更新成功")
        
        # ステップ4: アプリを公開
        print(f"\n[ステップ4] アプリを公開（プレビュー→本番）...")
        
        deploy_url = f"{base_url}/preview/app/deploy.json"
        deploy_payload = {
            "apps": [{"app": app_id}]
        }
        
        response = requests.post(deploy_url, headers=headers, json=deploy_payload, timeout=60)
        
        if response.status_code == 200:
            print(f"✅ アプリ公開成功")
            
            print(f"\n" + "=" * 60)
            print(f"✅ 完了しました")
            print(f"=" * 60)
            
            print(f"\n変更されたフィールド:")
            for change in changes:
                print(change)
            
            print(f"\n次のステップ:")
            print(f"1. Kintoneでアプリを開いて確認")
            print(f"2. フィールドマッピングを削除（もう不要）:")
            print(f"   # src/services/kintone_field_mappings.py の {app_id} セクション")
            print(f"3. データ同期を再実行:")
            print(f"   python scripts/sync_db_to_kintone.py {config['name']}")
            
        else:
            print(f"❌ アプリ公開エラー: {response.status_code}")
            print(f"レスポンス: {response.text}")
            print(f"\n手動でアプリを公開してください:")
            print(f"1. Kintoneでアプリを開く")
            print(f"2. 「設定」→「アプリを更新」をクリック")
            sys.exit(1)
    else:
        print(f"❌ フィールド更新エラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        
        # よくあるエラーの説明
        if response.status_code == 403:
            print(f"\n💡 ヒント: APIトークンに「アプリの設定」権限がありません")
            print(f"Kintoneでアプリ設定→APIトークン→権限を確認してください")
        
        sys.exit(1)

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
