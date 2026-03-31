"""App171（請求書）にPDF URL保存用のLINKフィールドを追加する。

既にURL保存向けLINKフィールドが存在する場合は何もしない。
存在しない場合は `invoice_pdf_url` フィールドを追加して deploy する。
"""

from __future__ import annotations

import base64
import os
import sys

import requests
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(override=True)

    subdomain = os.getenv("KINTONE_SUBDOMAIN", "").strip()
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID", "").strip()
    admin_user = os.getenv("KINTONE_ADMIN_USER", "").strip()
    admin_password = os.getenv("KINTONE_ADMIN_PASSWORD", "").strip()
    app_id = int(os.getenv("KINTONE_APP_INVOICES", "171"))

    if not subdomain or not admin_user or not admin_password:
        print("❌ 必須環境変数不足: KINTONE_SUBDOMAIN / KINTONE_ADMIN_USER / KINTONE_ADMIN_PASSWORD")
        sys.exit(1)

    if guest_space_id:
        base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    else:
        base_url = f"https://{subdomain}.cybozu.com/k/v1"

    auth = base64.b64encode(f"{admin_user}:{admin_password}".encode()).decode()
    headers = {
        "X-Cybozu-Authorization": auth,
        "Content-Type": "application/json",
    }
    headers_get = {"X-Cybozu-Authorization": auth}

    fields_resp = requests.get(
        f"{base_url}/app/form/fields.json",
        headers=headers_get,
        params={"app": app_id},
        timeout=30,
    )
    fields_resp.raise_for_status()
    properties = fields_resp.json().get("properties", {})

    preferred_codes = {"invoice_pdf_url", "pdf_url", "estimate_pdf_url", "document_url"}
    existing_link_codes = [
        code
        for code, prop in properties.items()
        if prop and prop.get("type") == "LINK"
    ]

    existing_target_codes = [code for code in existing_link_codes if code in preferred_codes]
    if existing_target_codes:
        print(f"✅ App{app_id} には既にPDF URLフィールドがあります: {', '.join(existing_target_codes)}")
        return

    new_code = "invoice_pdf_url"
    payload = {
        "app": app_id,
        "properties": {
            new_code: {
                "type": "LINK",
                "code": new_code,
                "label": "見積書PDF URL",
                "protocol": "WEB",
                "required": False,
                "unique": False,
            }
        },
    }

    add_resp = requests.post(
        f"{base_url}/preview/app/form/fields.json",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if add_resp.status_code >= 400:
        print("❌ フィールド追加失敗:", add_resp.status_code)
        print(add_resp.text)
    add_resp.raise_for_status()

    deploy_resp = requests.post(
        f"{base_url}/preview/app/deploy.json",
        headers=headers,
        json={"apps": [{"app": app_id}]},
        timeout=60,
    )
    deploy_resp.raise_for_status()

    print(f"✅ App{app_id} にLINKフィールド `{new_code}` を追加し、デプロイを開始しました。")


if __name__ == "__main__":
    main()
