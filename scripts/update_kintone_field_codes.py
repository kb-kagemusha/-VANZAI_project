"""
Kintoneアプリのフィールドコードを一括設定

フィールドラベル（フィールド名）と同じフィールドコードに自動設定します

使用方法:
    python scripts/update_kintone_field_codes.py [アプリID]
    
    例: python scripts/update_kintone_field_codes.py 165
    
注意:
    - システムフィールド（レコード番号、作成者など）は変更できません
    - ステータス、カテゴリー、作業者などのプロセス管理フィールドはスキップします
    - 実行前にバックアップを取ることを推奨します
"""
import os
import sys
from pathlib import Path
import json
import requests
import re

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# コマンドライン引数
app_id = int(sys.argv[1]) if len(sys.argv) > 1 else 165

# アプリ名とトークンのマッピング
app_info = {
    165: {"name": "workers", "token_env": "KINTONE_TOKEN_WORKERS"},
    167: {"name": "clients", "token_env": "KINTONE_TOKEN_CLIENTS"},
    166: {"name": "sites", "token_env": "KINTONE_TOKEN_SITES"},
    163: {"name": "roles", "token_env": "KINTONE_TOKEN_ROLES"},
    164: {"name": "project_types", "token_env": "KINTONE_TOKEN_PROJECT_TYPES"},
}

print(f"=" * 60)
print(f"Kintoneフィールドコード一括設定 - アプリID: {app_id}")
print(f"=" * 60)

# 設定
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

# APIエンドポイント
if guest_space_id:
    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
else:
    base_url = f"https://{subdomain}.cybozu.com/k/v1"

# GETリクエスト用ヘッダー（Content-Typeは不要）
get_headers = {
    "X-Cybozu-API-Token": token
}

# PUT/POSTリクエスト用ヘッダー
headers = {
    "X-Cybozu-API-Token": token,
    "Content-Type": "application/json"
}

print(f"\nアプリ名: {info.get('name', 'unknown')}")

# ステップ1: 現在のフィールド定義を取得
print(f"\n[ステップ1] 現在のフィールド定義を取得中...")

# guest space用のURLは /k/guest/{id}/v1 
if guest_space_id:
    get_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1/app/form/fields.json"
else:
    get_url = f"{base_url}/app/form/fields.json"

print(f"DEBUG: URL = {get_url}")
print(f"DEBUG: params = app={app_id}")
print(f"DEBUG: headers = {get_headers}")

response = requests.get(get_url, headers=get_headers, params={"app": str(app_id)}, timeout=30)

if response.status_code != 200:
    print(f"❌ エラー: {response.status_code}")
    print(f"レスポンス: {response.text}")
    sys.exit(1)

data = response.json()
properties = data.get("properties", {})

print(f"✅ 取得成功: {len(properties)} フィールド")

# ステップ2: 変更が必要なフィールドを特定
print(f"\n[ステップ2] 変更が必要なフィールドを特定中...")

# システムフィールド（変更不可）
SYSTEM_FIELD_TYPES = {
    "CREATOR", "CREATED_TIME", "MODIFIER", "UPDATED_TIME", 
    "RECORD_NUMBER", "REVISION", "__REVISION__", "__ID__"
}

# プロセス管理フィールド（変更しない）
PROCESS_FIELD_TYPES = {
    "CATEGORY", "STATUS", "STATUS_ASSIGNEE"
}

# フィールドコードとして使えない文字を置き換える関数
def sanitize_field_code(label: str) -> str:
    """
    フィールドラベルを有効なフィールドコードに変換
    
    ルール:
    - 英数字とアンダースコアのみ
    - 先頭は英字
    - 最大64文字
    """
    # 日本語などを削除、スペースをアンダースコアに
    code = re.sub(r'[^a-zA-Z0-9_]', '_', label)
    
    # 連続するアンダースコアを1つに
    code = re.sub(r'_+', '_', code)
    
    # 先頭と末尾のアンダースコアを削除
    code = code.strip('_')
    
    # 先頭が数字なら'f_'を追加
    if code and code[0].isdigit():
        code = 'f_' + code
    
    # 空の場合はデフォルト
    if not code:
        code = 'field'
    
    # 最大64文字
    code = code[:64]
    
    return code.lower()

update_properties = {}
changes = []

for code, props in properties.items():
    field_type = props.get("type", "")
    label = props.get("label", "")
    
    # システムフィールドはスキップ
    if field_type in SYSTEM_FIELD_TYPES:
        continue
    
    # プロセス管理フィールドはスキップ
    if field_type in PROCESS_FIELD_TYPES:
        continue
    
    # ラベルが空の場合はスキップ
    if not label:
        print(f"  ⚠️ スキップ: {code} (ラベルが空)")
        continue
    
    # 新しいフィールドコードを生成
    new_code = sanitize_field_code(label)
    
    # 既に同じ場合はスキップ
    if code == new_code:
        continue
    
    # 重複チェック
    if new_code in properties and new_code != code:
        print(f"  ⚠️ スキップ: {code} → {new_code} (重複)")
        continue
    
    # 変更対象に追加
    update_properties[code] = {
        "type": field_type,
        "code": new_code,
        "label": label
    }
    
    changes.append(f"  {code:30s} → {new_code:30s} ({label})")

if not changes:
    print("✅ 変更が必要なフィールドはありません")
    sys.exit(0)

print(f"\n変更対象: {len(changes)} フィールド")
for change in changes:
    print(change)

# 確認
print(f"\n" + "=" * 60)
print(f"⚠️ 警告: フィールドコードを変更します")
print(f"=" * 60)
print(f"アプリID: {app_id}")
print(f"変更数: {len(changes)} フィールド")
print(f"\n実行してよろしいですか？")
print(f"  y: 実行する")
print(f"  n: キャンセル")

confirmation = input("\n選択 [y/n]: ").strip().lower()

if confirmation != 'y':
    print("\n❌ キャンセルしました")
    sys.exit(0)

# ステップ3: フィールドコードを更新
print(f"\n[ステップ3] フィールドコードを更新中...")

# guest space用のpreview APIは /k/guest/{id}/v1/preview/
if guest_space_id:
    put_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1/preview/app/form/fields.json"
else:
    put_url = f"{base_url}/preview/app/form/fields.json"

print(f"DEBUG: PUT URL = {put_url}")

payload = {
    "app": app_id,
    "properties": update_properties
}

print(f"DEBUG: payload keys = {list(payload.keys())}")
print(f"DEBUG: properties count = {len(update_properties)}")

try:
    response = requests.put(put_url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        print(f"✅ フィールドコード更新成功")
        
        # プレビュー環境に反映された
        print(f"\n[ステップ4] アプリを公開（プレビュー→本番）")
        
        # guest space用のdeploy APIは /k/guest/{id}/v1/preview/
        if guest_space_id:
            deploy_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1/preview/app/deploy.json"
        else:
            deploy_url = f"{base_url}/preview/app/deploy.json"
        
        print(f"DEBUG: DEPLOY URL = {deploy_url}")
            
        deploy_payload = {
            "apps": [
                {
                    "app": app_id
                }
            ]
        }
        
        print(f"DEBUG: deploy payload = {deploy_payload}")
        
        response = requests.post(deploy_url, headers=headers, json=deploy_payload, timeout=60)
        
        if response.status_code == 200:
            print(f"✅ アプリ公開成功")
            
            print(f"\n" + "=" * 60)
            print(f"✅ 完了しました")
            print(f"=" * 60)
            
            print(f"\n変更されたフィールドコード:")
            for change in changes:
                print(change)
            
            print(f"\n次のステップ:")
            print(f"1. Kintoneでアプリを開いて確認")
            print(f"2. データ同期スクリプトを再実行:")
            print(f"   python scripts/sync_db_to_kintone.py {info.get('name', 'workers')}")
            
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
        sys.exit(1)

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
