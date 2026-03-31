"""
全Kintoneアプリのフィールド定義を一括抽出

全アプリのフィールド情報をJSON出力し、
フィールドコード変更用のマッピングを生成します
"""
import os
import sys
from pathlib import Path
import requests
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"

# 全アプリ設定（.envから）
APPS = {
    "workers": {"id": 165, "token_env": "KINTONE_TOKEN_WORKERS"},
    "clients": {"id": 167, "token_env": "KINTONE_TOKEN_CLIENTS"},
    "sites": {"id": 166, "token_env": "KINTONE_TOKEN_SITES"},
    "roles": {"id": 163, "token_env": "KINTONE_TOKEN_ROLES"},
    "project_types": {"id": 164, "token_env": "KINTONE_TOKEN_PROJECT_TYPES"},
    "projects": {"id": 160, "token_env": "KINTONE_TOKEN_PROJECTS"},
    "actuals": {"id": 168, "token_env": "KINTONE_TOKEN_ACTUALS"},
    "assignments": {"id": 158, "token_env": "KINTONE_TOKEN_ASSIGNMENTS"},
    "shift_slots": {"id": 159, "token_env": "KINTONE_TOKEN_SHIFT_SLOTS"},
    "price_sales": {"id": 162, "token_env": "KINTONE_TOKEN_PRICE_SALES"},
    "price_outsource": {"id": 161, "token_env": "KINTONE_TOKEN_PRICE_OUTSOURCE"},
    "price_rules": {"id": 157, "token_env": "KINTONE_TOKEN_PRICE_RULES"},
    "expenses": {"id": 151, "token_env": "KINTONE_TOKEN_EXPENSES"},
    "incentives": {"id": 150, "token_env": "KINTONE_TOKEN_INCENTIVES"},
    "incentive_rules": {"id": 155, "token_env": "KINTONE_TOKEN_INCENTIVE_RULES"},
    "bank_transfer_batches": {"id": 148, "token_env": "KINTONE_TOKEN_BANK_TRANSFER_BATCHES"},
    "payout_deliveries": {"id": None, "token_env": "KINTONE_TOKEN_PAYOUT_DELIVERIES"},  # ID不明
}


def get_fields(app_id: int, api_token: str):
    """フィールド定義取得"""
    url = f"{BASE_URL}/app/form/fields.json"
    headers = {"X-Cybozu-API-Token": api_token}
    params = {"app": app_id}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["properties"]


def main():
    print("=" * 60)
    print("全Kintoneアプリ フィールド定義抽出")
    print("=" * 60)
    print()
    
    output_dir = project_root / "kintone_app" / "field_mappings"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    for app_name, config in APPS.items():
        app_id = config["id"]
        if app_id is None:
            print(f"⏭️  {app_name:25} - アプリID不明（スキップ）")
            continue
        
        api_token = os.getenv(config["token_env"])
        if not api_token:
            print(f"⚠️  {app_name:25} - APIトークン未設定（スキップ）")
            continue
        
        try:
            print(f"📥 {app_name:25} (ID: {app_id})...", end=" ")
            fields = get_fields(app_id, api_token)
            
            # カスタムフィールドのみ抽出
            custom_fields = {
                code: field for code, field in fields.items()
                if not code.startswith("$")  # システムフィールド除外
            }
            
            # JSON保存
            output_file = output_dir / f"{app_name}_fields.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(custom_fields, f, ensure_ascii=False, indent=2)
            
            results[app_name] = {
                "app_id": app_id,
                "total_fields": len(fields),
                "custom_fields": len(custom_fields),
                "file": str(output_file)
            }
            
            print(f"✅ {len(custom_fields)} フィールド")
            
        except Exception as e:
            print(f"❌ エラー: {e}")
            results[app_name] = {"error": str(e)}
    
    print()
    print("=" * 60)
    print("抽出完了")
    print("=" * 60)
    print()
    print("結果サマリ:")
    for app_name, result in results.items():
        if "error" in result:
            print(f"  ❌ {app_name:25} - {result['error']}")
        else:
            print(f"  ✅ {app_name:25} - {result['custom_fields']} フィールド")
    
    print()
    print(f"出力先: {output_dir}")
    print()
    print("次のステップ:")
    print("1. field_mappings/*.json を確認")
    print("2. update_kintone_field_types.py に設定追加")
    print("3. フィールドコード変更実行")


if __name__ == "__main__":
    main()
