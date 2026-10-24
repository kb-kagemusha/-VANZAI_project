import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

subdomain = os.getenv('KINTONE_SUBDOMAIN')
guest_space_id = os.getenv('KINTONE_GUEST_SPACE_ID')
admin_user = os.getenv('KINTONE_ADMIN_USER')
admin_password = os.getenv('KINTONE_ADMIN_PASSWORD')

base_url = f'https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1'
auth_string = base64.b64encode(f'{admin_user}:{admin_password}'.encode()).decode()
headers = {'X-Cybozu-Authorization': auth_string}

# アプリ情報
r = requests.get(f'{base_url}/app.json', headers=headers, params={'id': '187'}, timeout=30)
print(f'アプリ情報ステータス: {r.status_code}')
if r.status_code == 200:
    app_data = r.json()
    print(f'アプリ名: {app_data.get("name", "")}')
    print(f'アプリコード: {app_data.get("code", "")}')
    print()
else:
    print(r.text)

# フィールド一覧
r = requests.get(f'{base_url}/app/form/fields.json', headers=headers, params={'app': '187'}, timeout=30)
print(f'フィールド取得ステータス: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    fields = data.get('properties', {})
    print(f'フィールド数: {len(fields)}')
    print('\n=== ユーザー定義フィールド ===')
    for code, field in fields.items():
        ftype = field.get('type', '')
        # システムフィールドをスキップ
        if ftype in ['RECORD_NUMBER', 'CREATOR', 'CREATED_TIME', 'MODIFIER', 'UPDATED_TIME',
                     'STATUS', 'STATUS_ASSIGNEE', 'CATEGORY']:
            continue
        label = field.get('label', '')
        print(f'{code:30s} | {ftype:20s} | {label}')
else:
    print(r.text)
