import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

subdomain = os.getenv('KINTONE_SUBDOMAIN')
admin_user = os.getenv('KINTONE_ADMIN_USER')
admin_password = os.getenv('KINTONE_ADMIN_PASSWORD')

# 通常スペースのアプリ187
base_url = f'https://{subdomain}.cybozu.com/k/v1'
auth_string = base64.b64encode(f'{admin_user}:{admin_password}'.encode()).decode()
headers = {'X-Cybozu-Authorization': auth_string}

# アプリ187の情報
r = requests.get(f'{base_url}/app.json', headers=headers, params={'id': '187'}, timeout=30)
print(f'ステータス: {r.status_code}')
if r.status_code == 200:
    app_data = r.json()
    print(f'アプリ名: {app_data.get("name", "")}')
    print(f'アプリコード: {app_data.get("code", "")}')
    print()
    
    # フィールド一覧
    r2 = requests.get(f'{base_url}/app/form/fields.json', headers=headers, params={'app': '187'}, timeout=30)
    if r2.status_code == 200:
        data = r2.json()
        fields = data.get('properties', {})
        print(f'フィールド数: {len(fields)}')
        print('\n=== 全フィールド ===')
        for code, field in fields.items():
            ftype = field.get('type', '')
            label = field.get('label', '')
            print(f'{code:30s} | {ftype:20s} | {label}')
else:
    print(f'エラー: {r.text}')
