#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""App174に front_dashboard + front_portal を同時適用する"""
import base64
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
load_dotenv(project_root / '.env')

SUBDOMAIN = os.getenv('KINTONE_SUBDOMAIN', 'xtf5wpxp3gk2')
GUEST_SPACE = os.getenv('KINTONE_GUEST_SPACE_ID', '3')
ADMIN_USER = os.getenv('KINTONE_ADMIN_USER', '')
ADMIN_PASS = os.getenv('KINTONE_ADMIN_PASSWORD', '')
APP_ID = int(os.getenv('KINTONE_APP_FRONT_DASHBOARD', '174'))

FRONT_DASHBOARD_JS = project_root / 'kintone_app' / 'customizations' / 'front_dashboard.js'
FRONT_PORTAL_JS = project_root / 'kintone_app' / 'customizations' / 'front_portal.js'
FRONT_PORTAL_CSS = project_root / 'kintone_app' / 'customizations' / 'front_portal.css'

BASE_V1 = f'https://{SUBDOMAIN}.cybozu.com/k/v1'
BASE_GUEST = f'https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE}/v1'
ADMIN_AUTH = base64.b64encode(f'{ADMIN_USER}:{ADMIN_PASS}'.encode()).decode()
HEADERS = {'X-Cybozu-Authorization': ADMIN_AUTH}


def upload_file(path: Path, content_type: str) -> str:
    with open(path, 'rb') as f:
        files = {'file': (path.name, f, content_type)}
        resp = requests.post(f'{BASE_V1}/file.json', headers=HEADERS, files=files, timeout=30)
    if not resp.ok:
        print(f'❌ upload failed: {path.name} {resp.status_code} {resp.text[:300]}')
        sys.exit(1)
    file_key = resp.json().get('fileKey', '')
    print(f'✅ uploaded: {path.name} -> {file_key}')
    return file_key


def main():
    for path in [FRONT_DASHBOARD_JS, FRONT_PORTAL_JS, FRONT_PORTAL_CSS]:
        if not path.exists():
            print(f'❌ file missing: {path}')
            sys.exit(1)

    dashboard_js_key = upload_file(FRONT_DASHBOARD_JS, 'text/javascript')
    portal_js_key = upload_file(FRONT_PORTAL_JS, 'text/javascript')
    portal_css_key = upload_file(FRONT_PORTAL_CSS, 'text/css')

    payload = {
        'app': str(APP_ID),
        'desktop': {
            'js': [
                {'type': 'FILE', 'file': {'fileKey': dashboard_js_key}},
                {'type': 'FILE', 'file': {'fileKey': portal_js_key}},
            ],
            'css': [
                {'type': 'FILE', 'file': {'fileKey': portal_css_key}},
            ],
        },
        'mobile': {'js': [], 'css': []},
    }

    set_resp = requests.put(
        f'{BASE_GUEST}/preview/app/customize.json',
        headers={**HEADERS, 'Content-Type': 'application/json'},
        data=json.dumps(payload),
        timeout=30,
    )
    if not set_resp.ok:
        print(f'❌ customize set failed: {set_resp.status_code} {set_resp.text[:300]}')
        sys.exit(1)
    print(f'✅ customize set: {set_resp.text}')

    deploy_payload = {'apps': [{'app': str(APP_ID), 'revision': '-1'}]}
    deploy_resp = requests.post(
        f'{BASE_GUEST}/preview/app/deploy.json',
        headers={**HEADERS, 'Content-Type': 'application/json'},
        data=json.dumps(deploy_payload),
        timeout=60,
    )
    if not deploy_resp.ok:
        print(f'❌ deploy failed: {deploy_resp.status_code} {deploy_resp.text[:300]}')
        sys.exit(1)

    print('✅ deploy done')


if __name__ == '__main__':
    main()
