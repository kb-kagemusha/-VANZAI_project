"""Kintone不足フィールド追加

対象（既存運用 + App174フロント要件）:
- shift_slots (159): shift_label
- actuals (168): status, period_key, sales_count
- workers (165): introducer_supplier_id, affiliation
- sites (166): category_major, category_middle, category_minor
- project_assignments (307): sales_flag, playing_manager, director, assistant_director, field_staff

使用方法:
    python scripts/add_kintone_missing_fields.py
"""
import os
import sys
from pathlib import Path
import requests
import base64

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(override=True)

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
ADMIN_USER = os.getenv("KINTONE_ADMIN_USER")
ADMIN_PASSWORD = os.getenv("KINTONE_ADMIN_PASSWORD")

if not SUBDOMAIN:
    print("❌ KINTONE_SUBDOMAIN が設定されていません")
    sys.exit(1)

if GUEST_SPACE_ID:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
else:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/v1"

APPS = {
    "shift_slots": {
        "app_id": int(os.getenv("KINTONE_APP_SHIFT_SLOTS", "159")),
        "token": os.getenv("KINTONE_TOKEN_SHIFT_SLOTS"),
        "fields": {
            "shift_label": {
                "type": "SINGLE_LINE_TEXT",
                "code": "shift_label",
                "label": "シフトラベル",
            }
        },
    },
    "actuals": {
        "app_id": int(os.getenv("KINTONE_APP_ACTUALS", "168")),
        "token": os.getenv("KINTONE_TOKEN_ACTUALS"),
        "fields": {
            "status": {
                "type": "DROP_DOWN",
                "code": "status",
                "label": "ステータス",
                "options": {
                    "active": {"label": "active", "index": "0"},
                    "invalid": {"label": "invalid", "index": "1"},
                    "superseded": {"label": "superseded", "index": "2"},
                },
                "defaultValue": "active",
            },
            "period_key": {
                "type": "SINGLE_LINE_TEXT",
                "code": "period_key",
                "label": "期間キー(YYYYMM)",
            },
            "sales_count": {
                "type": "NUMBER",
                "code": "sales_count",
                "label": "販売数",
            },
        },
    },
    "sites": {
        "app_id": int(os.getenv("KINTONE_APP_SITES", "166")),
        "token": os.getenv("KINTONE_TOKEN_SITES"),
        "fields": {
            "category_major": {
                "type": "SINGLE_LINE_TEXT",
                "code": "category_major",
                "label": "大カテゴリ",
            },
            "category_middle": {
                "type": "SINGLE_LINE_TEXT",
                "code": "category_middle",
                "label": "中カテゴリ",
            },
            "category_minor": {
                "type": "SINGLE_LINE_TEXT",
                "code": "category_minor",
                "label": "小カテゴリ",
            },
        },
    },
    "project_assignments": {
        "app_id": int(os.getenv("KINTONE_APP_PROJECT_ASSIGNMENTS", "307")),
        "token": os.getenv("KINTONE_TOKEN_PROJECT_ASSIGNMENTS"),
        "fields": {
            "sales_flag": {
                "type": "DROP_DOWN",
                "code": "sales_flag",
                "label": "販売",
                "options": {
                    "あり": {"label": "あり", "index": "0"},
                    "なし": {"label": "なし", "index": "1"},
                },
                "defaultValue": "なし",
            },
            "playing_manager": {
                "type": "SINGLE_LINE_TEXT",
                "code": "playing_manager",
                "label": "プレイングマネージャー",
            },
            "director": {
                "type": "SINGLE_LINE_TEXT",
                "code": "director",
                "label": "ディレクター",
            },
            "assistant_director": {
                "type": "SINGLE_LINE_TEXT",
                "code": "assistant_director",
                "label": "アシスタントディレクター",
            },
            "field_staff": {
                "type": "SINGLE_LINE_TEXT",
                "code": "field_staff",
                "label": "スタッフ",
            },
        },
    },
    "suppliers": {
        "app_id": int(os.getenv("KINTONE_APP_SUPPLIERS", "0")),
        "token": os.getenv("KINTONE_TOKEN_SUPPLIERS"),
        "fields": {
            "supplier_id": {
                "type": "SINGLE_LINE_TEXT",
                "code": "supplier_id",
                "label": "紹介者ID",
            },
            "name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "name",
                "label": "紹介者名",
            },
            "contact_email": {
                "type": "SINGLE_LINE_TEXT",
                "code": "contact_email",
                "label": "連絡先メール",
            },
            "contact_phone": {
                "type": "SINGLE_LINE_TEXT",
                "code": "contact_phone",
                "label": "連絡先電話",
            },
            "payout_terms_days": {
                "type": "NUMBER",
                "code": "payout_terms_days",
                "label": "支払サイト（日数）",
                "defaultValue": "70",
            },
            "default_daily_price": {
                "type": "NUMBER",
                "code": "default_daily_price",
                "label": "日額単価",
            },
            "is_active": {
                "type": "DROP_DOWN",
                "code": "is_active",
                "label": "有効フラグ",
                "options": {
                    "有効": {"label": "有効", "index": "0"},
                    "無効": {"label": "無効", "index": "1"},
                },
                "defaultValue": "有効",
            },
            "notes": {
                "type": "MULTI_LINE_TEXT",
                "code": "notes",
                "label": "備考",
            },
        },
    },
}


def infer_suppliers_supplier_id_field_type() -> str | None:
    """suppliersアプリの supplier_id フィールド型を推測する。

    Returns:
        "NUMBER" / "SINGLE_LINE_TEXT" などのKintone field type、または None。
    """
    suppliers_token = os.getenv("KINTONE_TOKEN_SUPPLIERS")
    suppliers_app_id = int(os.getenv("KINTONE_APP_SUPPLIERS", "0"))
    if not suppliers_token or not suppliers_app_id:
        return None

    try:
        fields = get_fields(suppliers_app_id, suppliers_token)
        supplier_id_props = fields.get("supplier_id")
        if isinstance(supplier_id_props, dict):
            field_type = supplier_id_props.get("type")
            if isinstance(field_type, str):
                return field_type
    except Exception:
        return None
    return None


def build_workers_app_config() -> dict | None:
    token = os.getenv("KINTONE_TOKEN_WORKERS")
    app_id = int(os.getenv("KINTONE_APP_WORKERS", "165"))
    if not token:
        return None

    suppliers_field_type = infer_suppliers_supplier_id_field_type()
    # introducer_supplier_id は DBの suppliers.id（ULID文字列）を参照するため、基本は文字列(1行)。
    field_type = "SINGLE_LINE_TEXT"
    if suppliers_field_type and suppliers_field_type != "SINGLE_LINE_TEXT":
        print(
            "⚠️ suppliers.supplier_id の型が SINGLE_LINE_TEXT ではありません。"
            " introducer_supplier_id は ULID文字列前提のため、SINGLE_LINE_TEXT で作成します。"
        )

    return {
        "app_id": app_id,
        "token": token,
        "fields": {
            "affiliation": {
                "type": "DROP_DOWN",
                "code": "affiliation",
                "label": "所属",
                "options": {
                    "現場": {"label": "現場", "index": "0"},
                    "VANZAI": {"label": "VANZAI", "index": "1"},
                },
                "defaultValue": "現場",
            },
            "introducer_supplier_id": {
                "type": field_type,
                "code": "introducer_supplier_id",
                "label": "紹介者（下請けID）",
            }
        },
    }


def build_headers(token: str | None, use_admin: bool) -> dict:
    if use_admin:
        auth_string = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
        return {"X-Cybozu-Authorization": auth_string}
    if token:
        return {"X-Cybozu-API-Token": token}
    return {}


def get_fields(app_id: int, token: str | None, use_admin: bool):
    url = f"{BASE_URL}/app/form/fields.json"
    headers = build_headers(token, use_admin)
    resp = requests.get(url, headers=headers, params={"app": app_id}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("properties", {})


def add_fields_preview(app_id: int, token: str | None, use_admin: bool, fields: dict):
    url = f"{BASE_URL}/preview/app/form/fields.json"
    headers = build_headers(token, use_admin)
    headers["Content-Type"] = "application/json"
    payload = {"app": app_id, "properties": fields}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def deploy(app_id: int, token: str | None, use_admin: bool):
    url = f"{BASE_URL}/preview/app/deploy.json"
    headers = build_headers(token, use_admin)
    headers["Content-Type"] = "application/json"
    payload = {"apps": [{"app": app_id}]}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


# workers（introducer_supplier_id）は suppliers の supplier_id の型に合わせて追加する
workers_config = build_workers_app_config()
if workers_config:
    APPS["workers"] = workers_config


use_admin = bool(ADMIN_USER and ADMIN_PASSWORD)

for name, config in APPS.items():
    token = config["token"]
    app_id = config["app_id"]
    if (not token and not use_admin) or not app_id:
        print(f"❌ {name}: APIトークンが未設定")
        continue

    print("=" * 60)
    print(f"{name} フィールド追加")
    print("=" * 60)
    print(f"アプリID: {app_id}")

    current_fields = get_fields(app_id, token, use_admin)
    to_add = {}
    for code, props in config["fields"].items():
        if code in current_fields:
            print(f"⏭️ 既存: {code}")
            continue
        to_add[code] = props

    if not to_add:
        print("✅ 追加対象なし")
        continue

    print(f"追加フィールド: {', '.join(to_add.keys())}")
    add_fields_preview(app_id, token, use_admin, to_add)
    print("✅ プレビュー追加完了")
    deploy(app_id, token, use_admin)
    print("✅ 本番反映完了")

print("=" * 60)
print("✅ 不足フィールド追加 完了")
print("=" * 60)
