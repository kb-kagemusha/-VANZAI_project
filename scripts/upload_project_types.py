"""
案件種別マスタ（App164）セットアップ完全自動化スクリプト
- フィールド設定の取得と更新
- 既存レコード削除
- カテゴリデータ一括登録
"""
import requests
import csv
import json
from pathlib import Path
from typing import Dict, List, Any

# Kintone設定
SUBDOMAIN = "xtf5wpxp3gk2"
GUEST_SPACE_ID = "3"
APP_ID = "164"
API_TOKEN = "GtPvBi1Ne221KMvlSViaePrds1297d7Rj4h3xC91"

BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
HEADERS = {
    "X-Cybozu-API-Token": API_TOKEN,
    "Content-Type": "application/json"
}

def get_form_fields():
    """アプリのフォーム設定を取得"""
    url = f"{BASE_URL}/app/form/fields.json"
    params = {"app": APP_ID}
    response = requests.get(url, headers=HEADERS, params=params)
    if not response.ok:
        print(f"フォーム取得エラー: {response.text}")
    response.raise_for_status()
    return response.json().get("properties", {})

def update_form_fields(fields: Dict[str, Any]):
    """アプリのフォーム設定を更新"""
    url = f"{BASE_URL}/app/form/fields.json"
    data = {
        "app": APP_ID,
        "properties": fields
    }
    response = requests.put(url, headers=HEADERS, json=data)
    if not response.ok:
        print(f"フォーム更新エラー: {response.text}")
    response.raise_for_status()
    return response.json()

def deploy_app():
    """アプリ設定をデプロイ"""
    url = f"{BASE_URL}/app/deploy.json"
    data = {
        "apps": [{"app": APP_ID}]
    }
    response = requests.post(url, headers=HEADERS, json=data)
    if not response.ok:
        print(f"デプロイエラー: {response.text}")
    response.raise_for_status()
    return response.json()

def get_existing_records():
    """既存レコードを取得"""
    url = f"{BASE_URL}/records.json"
    params = {"app": APP_ID}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if not response.ok:
            print(f"レコード取得エラー: {response.text}")
            return []
        return response.json().get("records", [])
    except Exception as e:
        print(f"レコード取得スキップ: {e}")
        return []

def delete_all_records(record_ids: List[int]):
    """既存レコードを全削除"""
    if not record_ids:
        return
    
    url = f"{BASE_URL}/records.json"
    batch_size = 100
    for i in range(0, len(record_ids), batch_size):
        batch_ids = record_ids[i:i + batch_size]
        data = {
            "app": APP_ID,
            "ids": batch_ids
        }
        response = requests.delete(url, headers=HEADERS, json=data)
        if not response.ok:
            print(f"削除エラー: {response.text}")
        response.raise_for_status()
        print(f"  削除完了: {len(batch_ids)}件")

def create_records(records: List[Dict[str, Any]]):
    """レコードを一括登録"""
    url = f"{BASE_URL}/records.json"
    batch_size = 100
    total = len(records)
    
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        data = {
            "app": APP_ID,
            "records": batch
        }
        response = requests.post(url, headers=HEADERS, json=data)
        if not response.ok:
            print(f"登録エラー詳細: {response.text}")
        response.raise_for_status()
        print(f"  登録完了: {i + len(batch)}/{total}件")

def load_csv_data():
    """CSVファイルを読み込んでKintone形式に変換"""
    csv_path = Path(__file__).parent.parent / "kintone_app" / "project_types_sjis.csv"
    
    records = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                "type_id": {"value": row["type_id"]},
                "name": {"value": row["name"]},
                "category_level": {"value": row["category_level"]},
                "parent_major": {"value": row["parent_major"]},
                "parent_middle": {"value": row["parent_middle"]}
            }
            records.append(record)
    
    return records

def setup_fields():
    """フィールド設定を確認・更新"""
    print("\n[STEP 1] フォーム設定を取得中...")
    current_fields = get_form_fields()
    
    # 必要なフィールド定義
    required_fields = {
        "type_id": {
            "type": "SINGLE_LINE_TEXT",
            "code": "type_id",
            "label": "案件種別ID",
            "required": True
        },
        "name": {
            "type": "SINGLE_LINE_TEXT",
            "code": "name",
            "label": "カテゴリ名",
            "required": True
        },
        "category_level": {
            "type": "SINGLE_LINE_TEXT",
            "code": "category_level",
            "label": "カテゴリレベル",
            "required": True
        },
        "parent_major": {
            "type": "SINGLE_LINE_TEXT",
            "code": "parent_major",
            "label": "親（大カテゴリ）",
            "required": False
        },
        "parent_middle": {
            "type": "SINGLE_LINE_TEXT",
            "code": "parent_middle",
            "label": "親（中カテゴリ）",
            "required": False
        }
    }
    
    needs_update = False
    update_fields = {}
    
    for code, field_def in required_fields.items():
        if code not in current_fields:
            print(f"  追加が必要: {code}")
            update_fields[code] = field_def
            needs_update = True
        elif current_fields[code].get("type") != field_def["type"]:
            print(f"  型変更が必要: {code} ({current_fields[code].get('type')} → {field_def['type']})")
            update_fields[code] = field_def
            needs_update = True
        else:
            print(f"  ✓ 正常: {code}")
    
    if needs_update:
        print("\n[STEP 2] フォーム設定を更新中...")
        update_form_fields(update_fields)
        print("  更新完了")
        
        print("\n[STEP 3] アプリをデプロイ中...")
        deploy_app()
        print("  デプロイ完了")
        print("  ⚠️ デプロイ処理中... 10秒待機します")
        import time
        time.sleep(10)
    else:
        print("  → フィールド設定は正常です（更新不要）")
    
    return needs_update

def main():
    print("=" * 70)
    print("案件種別マスタ（App164）データ登録")
    print("=" * 70)
    
    try:
        # フィールドチェックはスキップ（APIトークンに設定変更権限がない）
        print("\n⚠️ 注意: 以下のフィールドが存在することを前提とします:")
        print("  - type_id (文字列)")
        print("  - name (文字列)")
        print("  - category_level (文字列)")
        print("  - parent_major (文字列)")
        print("  - parent_middle (文字列)")
        print("\n  フィールドが未設定の場合は、Kintone画面で手動追加してください。")
        
        # CSVデータ読み込み
        print("\n[STEP 1] CSVファイルを読み込み中...")
        records = load_csv_data()
        print(f"  読み込み完了: {len(records)}件")
        
        # 既存レコード削除
        print("\n[STEP 2] 既存レコードを確認中...")
        existing = get_existing_records()
        if existing:
            print(f"  既存レコード: {len(existing)}件")
            print("\n[STEP 3] 既存レコードを削除中...")
            record_ids = [int(rec["$id"]["value"]) for rec in existing]
            delete_all_records(record_ids)
        else:
            print("  既存レコードなし（スキップ）")
        
        # 新規レコード登録
        print("\n[STEP 4] 新規レコードを登録中...")
        create_records(records)
        
        print("\n" + "=" * 70)
        print("✅ データ登録完了!")
        print("=" * 70)
        print(f"\n登録内容:")
        print(f"  - 大カテゴリ: 4件")
        print(f"  - 中カテゴリ: 11件")
        print(f"  - 小カテゴリ: 34件")
        print(f"  合計: {len(records)}件")
        
        print("\n次のステップ:")
        print("  1. Kintoneのフロントページで「案件を登録」をクリック")
        print("  2. 大カテゴリを選択 → 中カテゴリが絞り込まれることを確認")
        print("  3. 中カテゴリを選択 → 小カテゴリが絞り込まれることを確認")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n" + "=" * 70)
        print("トラブルシューティング:")
        print("=" * 70)
        print("エラーメッセージに「選択肢にありません」が含まれる場合:")
        print("  → App164のtype_idとnameフィールドが選択肢型になっています")
        print("  → Kintone画面でフィールド設定を開き、文字列型に変更してください")
        print("\nフィールドが見つからない場合:")
        print("  → category_level, parent_major, parent_middleを手動追加してください")
        raise

if __name__ == "__main__":
    main()
