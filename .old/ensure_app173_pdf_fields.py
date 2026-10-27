#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import os

import requests
from dotenv import load_dotenv

APP_ID = "173"


def kintone_base_and_headers():
    load_dotenv()
    sub = os.getenv("KINTONE_SUBDOMAIN")
    guest = os.getenv("KINTONE_GUEST_SPACE_ID")
    user = os.getenv("KINTONE_ADMIN_USER")
    password = os.getenv("KINTONE_ADMIN_PASSWORD")
    if not (sub and guest and user and password):
        raise RuntimeError("KINTONE_* env is missing")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    base = f"https://{sub}.cybozu.com/k/guest/{guest}/v1"
    headers = {
        "X-Cybozu-Authorization": auth,
        "Content-Type": "application/json",
    }
    return base, headers


def get_properties(base, headers):
    r = requests.get(
        f"{base}/app/form/fields.json",
        headers={"X-Cybozu-Authorization": headers["X-Cybozu-Authorization"]},
        params={"app": APP_ID},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("properties", {})


def add_field(base, headers, code, field_def):
    payload = {
        "app": APP_ID,
        "properties": {
            code: field_def
        }
    }
    r = requests.post(f"{base}/preview/app/form/fields.json", headers=headers, json=payload, timeout=30)
    r.raise_for_status()


def deploy(base, headers):
    payload = {
        "apps": [{"app": APP_ID}],
        "revert": False
    }
    r = requests.post(f"{base}/preview/app/deploy.json", headers=headers, json=payload, timeout=30)
    r.raise_for_status()


def main():
    base, headers = kintone_base_and_headers()
    props = get_properties(base, headers)
    changed = False

    if "payout_pdf" not in props:
        add_field(
            base,
            headers,
            "payout_pdf",
            {
                "type": "FILE",
                "code": "payout_pdf",
                "label": "支払明細PDF",
                "noLabel": False
            },
        )
        changed = True
        print("added payout_pdf (FILE)")
    else:
        print("exists payout_pdf")

    if "payout_pdf_url" not in props:
        add_field(
            base,
            headers,
            "payout_pdf_url",
            {
                "type": "LINK",
                "code": "payout_pdf_url",
                "label": "支払明細PDF URL",
                "protocol": "WEB",
                "noLabel": False
            },
        )
        changed = True
        print("added payout_pdf_url (LINK)")
    else:
        print("exists payout_pdf_url")

    if changed:
        deploy(base, headers)
        print("deploy started")
    else:
        print("no change")


if __name__ == "__main__":
    main()
