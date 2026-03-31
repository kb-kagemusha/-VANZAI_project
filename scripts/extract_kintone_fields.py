"""
Kintoneアプリのフィールド定義を取得してマッピング設定を生成

使用方法:
    python scripts/extract_kintone_fields.py [アプリID]
    
    例: python scripts/extract_kintone_fields.py 165
"""
import os
import sys
from pathlib import Path
import json
import requests

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
    148: {"name": "bank_transfer_batches", "token_env": "KINTONE_TOKEN_BANK_TRANSFER_BATCHES"},
    168: {"name": "actuals", "token_env": "KINTONE_TOKEN_ACTUALS"},
    160: {"name": "projects", "token_env": "KINTONE_TOKEN_PROJECTS"},
    158: {"name": "assignments", "token_env": "KINTONE_TOKEN_ASSIGNMENTS"},
    159: {"name": "shift_slots", "token_env": "KINTONE_TOKEN_SHIFT_SLOTS"},
    162: {"name": "price_sales", "token_env": "KINTONE_TOKEN_PRICE_SALES"},
    161: {"name": "price_outsource", "token_env": "KINTONE_TOKEN_PRICE_OUTSOURCE"},
    157: {"name": "price_rules", "token_env": "KINTONE_TOKEN_PRICE_RULES"},
    151: {"name": "expenses", "token_env": "KINTONE_TOKEN_EXPENSES"},
    150: {"name": "incentives", "token_env": "KINTONE_TOKEN_INCENTIVES"},
    147: {"name": "equipment", "token_env": "KINTONE_TOKEN_EQUIPMENT"},
    146: {"name": "equipment_loans", "token_env": "KINTONE_TOKEN_EQUIPMENT_LOANS"},
    171: {"name": "tasks", "token_env": "KINTONE_TOKEN_TASKS"},
    172: {"name": "project_documents", "token_env": "KINTONE_TOKEN_PROJECT_DOCUMENTS"},
    173: {"name": "incentive_rules", "token_env": "KINTONE_TOKEN_INCENTIVE_RULES"},
}

print(f"=" * 60)
print(f"Kintoneフィールド定義取得 - アプリID: {app_id}")
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
    url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1/app/form/fields.json"
else:
    url = f"https://{subdomain}.cybozu.com/k/v1/app/form/fields.json"

headers = {
    "X-Cybozu-API-Token": token
}

params = {
    "app": str(app_id)
}

print(f"\nアプリ名: {info.get('name', 'unknown')}")
print(f"URL: {url}")

try:
    # フィールド定義取得
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ エラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        sys.exit(1)
    
    data = response.json()
    properties = data.get("properties", {})
    
    print(f"\n✅ フィールド取得成功: {len(properties)} 件")
    
    print(f"\n" + "=" * 60)
    print("フィールド一覧:")
    print("=" * 60)
    
    # システムフィールドとカスタムフィールドを分ける
    custom_fields = []
    system_fields = []
    
    for code, props in properties.items():
        field_type = props.get("type", "")
        label = props.get("label", "")
        required = props.get("required", False)
        
        field_info = {
            "code": code,
            "type": field_type,
            "label": label,
            "required": required
        }
        
        # システムフィールドかどうか判定
        if field_type in ["CREATOR", "CREATED_TIME", "MODIFIER", "UPDATED_TIME", "RECORD_NUMBER", "REVISION"]:
            system_fields.append(field_info)
        else:
            custom_fields.append(field_info)
    
    # カスタムフィールドを表示
    print("\n【カスタムフィールド】")
    for field in sorted(custom_fields, key=lambda x: x["code"]):
        required_mark = " ※必須" if field["required"] else ""
        print(f"  {field['code']:30s} ({field['type']:20s}) {field['label']}{required_mark}")
    
    print(f"\n【システムフィールド】")
    for field in sorted(system_fields, key=lambda x: x["code"]):
        print(f"  {field['code']:30s} ({field['type']:20s}) {field['label']}")
    
    # JSONファイルに保存
    output_dir = project_root / "kintone_app" / "field_mappings"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"{info.get('name', f'app_{app_id}')}_fields.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "app_id": app_id,
            "app_name": info.get("name", "unknown"),
            "fields": custom_fields,
            "system_fields": system_fields
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n" + "=" * 60)
    print(f"✅ フィールド定義を保存しました")
    print(f"ファイル: {output_file}")
    print("=" * 60)
    
    # Pythonマッピング辞書を生成
    print(f"\n" + "=" * 60)
    print("Pythonマッピング辞書（コピペ用）:")
    print("=" * 60)
    
    print(f"\n# {info.get('name', 'unknown')} フィールドマッピング")
    print(f"{info.get('name', 'unknown').upper()}_FIELD_MAPPING = {{")
    
    # 推測マッピング（一般的な命名から）
    suggested_mappings = {
        "id": "worker_id",
        "name": "name",
        "氏名": "name",
        "名前": "name",
        "email": "email",
        "メール": "email",
        "phone": "phone",
        "電話": "phone",
        "address": "address",
        "住所": "address",
        "notes": "notes",
        "備考": "notes",
        "is_active": "is_active",
        "有効": "is_active",
    }
    
    for field in sorted(custom_fields, key=lambda x: x["code"]):
        # 推測される対応フィールド
        suggested = None
        code_lower = field['code'].lower()
        label_lower = field['label'].lower() if field['label'] else ""
        
        for key, value in suggested_mappings.items():
            if key in code_lower or key in label_lower:
                suggested = value
                break
        
        if suggested:
            print(f'    "{field["code"]}": "{suggested}",  # {field["label"]} → {suggested}')
        else:
            print(f'    "{field["code"]}": "???",  # {field["label"]} → 要設定')
    
    print("}")
    
except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
