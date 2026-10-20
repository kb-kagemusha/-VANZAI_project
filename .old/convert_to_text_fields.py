"""
Kintoneフィールドタイプを文字列（1行）に変換

DROP_DOWN/RADIO_BUTTON → SINGLE_LINE_TEXT に変更
選択肢制限を完全に削除します

使用方法:
    python scripts/convert_to_text_fields.py [アプリID]
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

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"

APP_CONFIGS = {
    165: {
        "name": "workers",
        "token_env": "KINTONE_TOKEN_WORKERS",
        "fields_to_convert": ["worker_id", "name", "phone"]
    },
    167: {
        "name": "clients",
        "token_env": "KINTONE_TOKEN_CLIENTS",
        "fields_to_convert": ["client_id", "name", "code", "address"]
    },
    166: {
        "name": "sites",
        "token_env": "KINTONE_TOKEN_SITES",
        "fields_to_convert": ["site_id", "name", "code", "address"]
    },
    163: {
        "name": "roles",
        "token_env": "KINTONE_TOKEN_ROLES",
        "fields_to_convert": ["role_id", "name", "description"]
    },
    164: {
        "name": "project_types",
        "token_env": "KINTONE_TOKEN_PROJECT_TYPES",
        "fields_to_convert": ["type_id", "name", "description"]
    },
}


def get_fields(app_id: int, api_token: str):
    """フィールド定義取得"""
    url = f"{BASE_URL}/app/form/fields.json"
    headers = {"X-Cybozu-API-Token": api_token}
    params = {"app": app_id}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["properties"]


def update_fields_preview(app_id: int, api_token: str, fields_to_update: dict):
    """プレビュー環境のフィールド更新"""
    url = f"{BASE_URL}/preview/app/form/fields.json"
    headers = {
        "X-Cybozu-API-Token": api_token,
        "Content-Type": "application/json"
    }
    
    data = {
        "app": app_id,
        "properties": fields_to_update
    }
    
    response = requests.put(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def deploy_app(app_id: int, api_token: str):
    """プレビュー → 本番環境デプロイ"""
    url = f"{BASE_URL}/preview/app/deploy.json"
    headers = {
        "X-Cybozu-API-Token": api_token,
        "Content-Type": "application/json"
    }
    
    data = {
        "apps": [{"app": app_id}],
        "revert": False
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def main():
    # コマンドライン引数チェック
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    if app_id not in APP_CONFIGS:
        print(f"❌ エラー: アプリID {app_id} の設定がありません")
        print(f"対応アプリ: {list(APP_CONFIGS.keys())}")
        sys.exit(1)
    
    config = APP_CONFIGS[app_id]
    api_token = os.getenv(config["token_env"])
    
    if not api_token:
        print(f"❌ エラー: {config['token_env']} が .env に設定されていません")
        sys.exit(1)
    
    print("=" * 60)
    print("Kintoneフィールドタイプ変換（→ SINGLE_LINE_TEXT）")
    print("=" * 60)
    print(f"アプリID: {app_id}")
    print(f"アプリ名: {config['name']}")
    print()
    
    # ステップ1: 現在のフィールド定義取得
    print("[ステップ1] 現在のフィールド定義を取得中...")
    fields = get_fields(app_id, api_token)
    print(f"✅ 取得成功: {len(fields)} フィールド")
    print()
    
    # ステップ2: 変換対象フィールド特定
    print("[ステップ2] 変換対象フィールドを特定中...")
    fields_to_update = {}
    
    for field_code in config["fields_to_convert"]:
        if field_code not in fields:
            print(f"⚠️ スキップ: {field_code} が存在しません")
            continue
        
        field = fields[field_code]
        current_type = field["type"]
        
        if current_type in ["DROP_DOWN", "RADIO_BUTTON", "CHECK_BOX"]:
            fields_to_update[field_code] = {
                "type": "SINGLE_LINE_TEXT",
                "code": field_code,
                "label": field["label"]
            }
            print(f"  {field_code:20} ({current_type:15}) → SINGLE_LINE_TEXT")
        else:
            print(f"  {field_code:20} ({current_type:15}) - 変換不要")
    
    if not fields_to_update:
        print("\n✅ 変換対象フィールドがありません")
        return
    
    print()
    print("=" * 60)
    print("⚠️ 警告: フィールドタイプを変更します")
    print("=" * 60)
    print(f"アプリID: {app_id} ({config['name']})")
    print(f"変更数: {len(fields_to_update)} フィールド")
    print()
    
    if not auto_confirm:
        confirm = input("実行してよろしいですか？ [y/n]: ")
        if confirm.lower() != 'y':
            print("中止しました")
            return
    else:
        print("自動実行モード（--yes指定）")
    
    # ステップ3: プレビュー更新
    print("[ステップ3] フィールドタイプを変更中（プレビュー）...")
    try:
        update_fields_preview(app_id, api_token, fields_to_update)
        print("✅ プレビュー更新成功")
    except Exception as e:
        print(f"❌ エラー: {e}")
        if hasattr(e, 'response'):
            print(f"レスポンス: {e.response.text}")
        sys.exit(1)
    
    print()
    
    # ステップ4: デプロイ
    print("[ステップ4] アプリを公開（プレビュー→本番）...")
    try:
        deploy_app(app_id, api_token)
        print("✅ アプリ公開成功")
    except Exception as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ 完了しました")
    print("=" * 60)
    print()
    print("変更されたフィールド:")
    for field_code in fields_to_update:
        print(f"  {field_code:20} → SINGLE_LINE_TEXT")
    print()
    print("次のステップ:")
    print("1. Kintoneでアプリを開いて確認")
    print("2. データ同期を実行:")
    print(f"   python scripts/sync_db_to_kintone.py {config['name']}")


if __name__ == "__main__":
    main()
