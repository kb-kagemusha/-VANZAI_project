"""
全Kintoneアプリのフィールドコードを英語に一括変更

カスタムフィールドのlabelを見て、それをフィールドコードに設定します
（labelが既に英語の場合、それを使用）

使用方法:
    python scripts/update_all_field_codes.py [--dry-run] [--yes]
    
    --dry-run: 変更内容を表示するのみ（実行しない）
    --yes, -y: 確認プロンプトをスキップ（自動承認）
"""
import os
import sys
from pathlib import Path
import requests
import json
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"

# 処理対象アプリ（既存5個は除外）
APPS_TO_PROCESS = {
    "projects": {"id": 160, "token_env": "KINTONE_TOKEN_PROJECTS"},
    "actuals": {"id": 168, "token_env": "KINTONE_TOKEN_ACTUALS"},
    "assignments": {"id": 158, "token_env": "KINTONE_TOKEN_ASSIGNMENTS"},
    "shift_slots": {"id": 159, "token_env": "KINTONE_TOKEN_SHIFT_SLOTS"},
    "price_sales": {"id": 162, "token_env": "KINTONE_TOKEN_PRICE_SALES"},
    "price_outsource": {"id": 161, "token_env": "KINTONE_TOKEN_PRICE_OUTSOURCE"},
    "price_rules": {"id": 157, "token_env": "KINTONE_TOKEN_PRICE_RULES"},
    "expenses": {"id": 151, "token_env": "KINTONE_TOKEN_EXPENSES"},
    "incentives": {"id": 150, "token_env": "KINTONE_TOKEN_INCENTIVES"},
    "bank_transfer_batches": {"id": 148, "token_env": "KINTONE_TOKEN_BANK_TRANSFER_BATCHES"},
    "equipment": {"id": 147, "token_env": "KINTONE_TOKEN_EQUIPMENT"},
    "equipment_loans": {"id": 146, "token_env": "KINTONE_TOKEN_EQUIPMENT_LOANS"},
    "tasks": {"id": 145, "token_env": "KINTONE_TOKEN_TASKS"},
    "project_documents": {"id": 144, "token_env": "KINTONE_TOKEN_PROJECT_DOCUMENTS"},
    "incentive_rules": {"id": 152, "token_env": "KINTONE_TOKEN_INCENTIVE_RULES"},
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


def normalize_field_code(label: str) -> str:
    """labelからフィールドコードを生成"""
    # 既に英語の場合はそのまま使用
    if label.replace("_", "").replace("-", "").isalnum() and not any(ord(c) > 127 for c in label):
        return label
    # 日本語の場合は変換不可
    return None


def main():
    dry_run = "--dry-run" in sys.argv
    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    
    print("=" * 60)
    print("全Kintoneアプリ フィールドコード英語化")
    print("=" * 60)
    if dry_run:
        print("⚠ DRY RUN モード（実行しません）")
    if auto_yes:
        print("自動承認モード（--yes）")
    print()
    
    results = {}
    
    for app_name, config in APPS_TO_PROCESS.items():
        app_id = config["id"]
        api_token = os.getenv(config["token_env"])
        
        if not api_token:
            print(f"⚠️ {app_name:25} - APIトークン未設定（スキップ）")
            continue
        
        print(f"\n{'='*60}")
        print(f"📱 アプリ: {app_name} (ID: {app_id})")
        print(f"{'='*60}")
        
        try:
            # ステップ1: フィールド定義取得
            print("[1] フィールド定義取得中...")
            fields = get_fields(app_id, api_token)
            print(f"    ✅ {len(fields)} フィールド")
            
            # ステップ2: 変更対象特定
            print("[2] 変更対象フィールド特定中...")
            fields_to_update = {}
            
            for field_code, field in fields.items():
                # システムフィールドをスキップ
                if field_code.startswith("$") or field["type"] in [
                    "RECORD_NUMBER", "CREATOR", "CREATED_TIME",
                    "MODIFIER", "UPDATED_TIME", "STATUS", "STATUS_ASSIGNEE",
                    "CATEGORY"
                ]:
                    continue
                
                # labelが英語の場合、それをフィールドコードに設定
                label = field.get("label", "")
                new_code = normalize_field_code(label)
                
                if new_code and new_code != field_code:
                    # 既存のフィールド設定を保持したまま、codeとlabelのみ変更
                    field_update = {k: v for k, v in field.items()}
                    field_update["code"] = new_code
                    field_update["label"] = new_code
                    fields_to_update[field_code] = field_update
                    
                    print(f"    {field_code:30} → {new_code}")
            
            if not fields_to_update:
                print("    ℹ️ 変更対象フィールドなし（スキップ）")
                continue
            
            print(f"\n    合計: {len(fields_to_update)} フィールド変更")
            
            if dry_run:
                print("    ⏭️ DRY RUN - 実行スキップ")
                continue
            
            # 確認プロンプト（自動承認モードでない場合のみ）
            if not auto_yes:
                print()
                confirm = input(f"    {app_name} を変更しますか？ [y/n]: ")
                if confirm.lower() != 'y':
                    print("    ⏭️ スキップ")
                    continue
            
            # ステップ3: プレビュー更新
            print("[3] プレビュー更新中...")
            update_fields_preview(app_id, api_token, fields_to_update)
            print("    ✅ プレビュー更新成功")
            
            # ステップ4: デプロイ
            print("[4] アプリ公開中...")
            deploy_app(app_id, api_token)
            print("    ✅ アプリ公開成功")
            
            results[app_name] = {"success": True, "fields_updated": len(fields_to_update)}
            
            # レート制限対策
            time.sleep(1)
            
        except Exception as e:
            print(f"    ❌ エラー: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"    レスポンス: {e.response.text[:200]}")
            results[app_name] = {"success": False, "error": str(e)}
    
    print()
    print("=" * 60)
    print("完了")
    print("=" * 60)
    print()
    print("結果サマリ:")
    for app_name, result in results.items():
        if result.get("success"):
            print(f"  ✅ {app_name:25} - {result['fields_updated']} フィールド更新")
        else:
            print(f"  ❌ {app_name:25} - {result.get('error', '不明なエラー')}")


if __name__ == "__main__":
    main()
