"""project_types の選択肢を更新

目的:
    - project_types の type_id/name/description を同期可能な選択肢に更新
    - Kintone側の選択肢制約で同期が失敗する問題を解消

使用方法:
    python scripts/update_project_types_options.py
"""
import os
import sys
from pathlib import Path
import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

APP_ID = int(os.getenv("KINTONE_APP_PROJECT_TYPES", "164"))
TOKEN = os.getenv("KINTONE_TOKEN_PROJECT_TYPES")
SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")

if not TOKEN:
    print("❌ KINTONE_TOKEN_PROJECT_TYPES が設定されていません")
    sys.exit(1)

if not SUBDOMAIN:
    print("❌ KINTONE_SUBDOMAIN が設定されていません")
    sys.exit(1)

if GUEST_SPACE_ID:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
else:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/v1"

GET_URL = f"{BASE_URL}/app/form/fields.json"
PUT_URL = f"{BASE_URL}/preview/app/form/fields.json"
DEPLOY_URL = f"{BASE_URL}/preview/app/deploy.json"

headers = {
    "X-Cybozu-API-Token": TOKEN,
    "Content-Type": "application/json",
}

print("=" * 60)
print("project_types 選択肢更新")
print("=" * 60)
print(f"アプリID: {APP_ID}")

# フィールド定義取得
resp = requests.get(GET_URL, headers={"X-Cybozu-API-Token": TOKEN}, params={"app": APP_ID}, timeout=30)
resp.raise_for_status()
properties = resp.json().get("properties", {})

# 更新対象
targets = {
    "type_id": ["PT01", "PT02", "PT03"],
    "name": ["案件種別PT01", "案件種別PT02", "案件種別PT03"],
    "description": ["ドライラン用種別1", "ドライラン用種別2", "ドライラン用種別3"],
}

update_properties = {}
for field_code, options in targets.items():
    field = properties.get(field_code)
    if not field:
        print(f"⚠️ フィールドが見つかりません: {field_code}")
        continue

    field_type = field.get("type")
    label = field.get("label", field_code)

    if field_type not in ("DROP_DOWN", "RADIO_BUTTON"):
        print(f"⚠️ 対象外のタイプ: {field_code} ({field_type})")
        continue

    option_map = {opt: {"label": opt, "index": str(i)} for i, opt in enumerate(options)}
    update_properties[field_code] = {
        "type": field_type,
        "code": field_code,
        "label": label,
        "options": option_map,
    }

    if field_type == "RADIO_BUTTON":
        update_properties[field_code]["defaultValue"] = options[0]

if not update_properties:
    print("❌ 更新対象がありません")
    sys.exit(1)

# プレビュー更新
print("[ステップ1] プレビュー更新...")
resp = requests.put(PUT_URL, headers=headers, json={"app": APP_ID, "properties": update_properties}, timeout=60)
if resp.status_code != 200:
    print(f"❌ エラー: {resp.status_code}")
    print(resp.text)
    sys.exit(1)
print("✅ プレビュー更新成功")

# デプロイ
print("[ステップ2] 本番へデプロイ...")
resp = requests.post(DEPLOY_URL, headers=headers, json={"apps": [{"app": APP_ID}]}, timeout=60)
if resp.status_code != 200:
    print(f"❌ エラー: {resp.status_code}")
    print(resp.text)
    sys.exit(1)

print("✅ デプロイ成功")
print("=" * 60)
print("✅ 完了")
print("=" * 60)
