"""App171/App173 のフォームレイアウトを正規フィールド優先で並べ替える。"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(override=True)

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
ADMIN_USER = os.getenv("KINTONE_ADMIN_USER")
ADMIN_PASSWORD = os.getenv("KINTONE_ADMIN_PASSWORD")

if not SUBDOMAIN or not ADMIN_USER or not ADMIN_PASSWORD:
    print("❌ 必須環境変数が不足しています")
    sys.exit(1)

if GUEST_SPACE_ID:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
else:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/v1"


def admin_headers(include_content_type: bool = False) -> dict[str, str]:
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    headers = {"X-Cybozu-Authorization": auth}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_layout(app_id: int) -> tuple[list[dict], str]:
    resp = requests.get(
        f"{BASE_URL}/app/form/layout.json",
        headers=admin_headers(False),
        params={"app": str(app_id)},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("layout", []), str(data.get("revision", "-1"))


def put_layout(app_id: int, layout: list[dict], revision: str) -> None:
    resp = requests.put(
        f"{BASE_URL}/preview/app/form/layout.json",
        headers=admin_headers(True),
        json={"app": app_id, "layout": layout, "revision": revision},
        timeout=60,
    )
    resp.raise_for_status()


def deploy(app_ids: list[int]) -> None:
    resp = requests.post(
        f"{BASE_URL}/preview/app/deploy.json",
        headers=admin_headers(True),
        json={"apps": [{"app": app_id} for app_id in app_ids]},
        timeout=60,
    )
    resp.raise_for_status()


def reorder_layout(layout: list[dict], priority_codes: list[str]) -> list[dict]:
    code_to_row: dict[str, dict] = {}
    ordered_codes: list[str] = []

    for row in layout:
        if row.get("type") != "ROW":
            continue
        fields = row.get("fields", [])
        if not fields:
            continue
        first = fields[0]
        code = first.get("code")
        if not code:
            continue
        code_to_row[code] = row
        ordered_codes.append(code)

    result: list[dict] = []
    used: set[str] = set()

    for code in priority_codes:
        row = code_to_row.get(code)
        if row is None:
            continue
        result.append(row)
        used.add(code)

    for code in ordered_codes:
        if code in used:
            continue
        result.append(code_to_row[code])

    return result


def summarize_codes(layout: list[dict]) -> list[str]:
    codes: list[str] = []
    for row in layout:
        if row.get("type") != "ROW":
            continue
        fields = row.get("fields", [])
        if not fields:
            continue
        code = fields[0].get("code")
        if code:
            codes.append(str(code))
    return codes


def main() -> None:
    priorities = {
        171: [
            "id",
            "client_id",
            "project_id",
            "period_key",
            "billing_date",
            "status",
            "document_type",
            "owner_name",
            "version",
            "parent_invoice_id",
            "subtotal",
            "tax_amount",
            "fixed_office_fee",
            "total_amount",
            "issued_at",
            "closed_at",
            "pdf_object_key",
            "notes",
        ],
        173: [
            "payout_id",
            "worker_id",
            "supplier_id",
            "project_id",
            "period_key",
            "payment_date",
            "status",
            "version",
            "parent_payout_id",
            "total_amount",
            "approved_at",
            "paid_at",
            "closed_at",
            "notes",
        ],
    }

    touched: list[int] = []

    for app_id, priority in priorities.items():
        layout, revision = get_layout(app_id)
        before = summarize_codes(layout)
        after_layout = reorder_layout(layout, priority)
        after = summarize_codes(after_layout)

        if before == after:
            print(f"app {app_id}: 並び変更なし")
            continue

        put_layout(app_id, after_layout, revision)
        touched.append(app_id)
        print(f"app {app_id}: preview更新 ({len(before)}行)")

    if touched:
        deploy(touched)
        print(f"deploy完了: {touched}")
    else:
        print("変更なし")

    for app_id in priorities.keys():
        layout, _ = get_layout(app_id)
        codes = summarize_codes(layout)
        print(f"app {app_id} 先頭10: {codes[:10]}")


if __name__ == "__main__":
    main()
