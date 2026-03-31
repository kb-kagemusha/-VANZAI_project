import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

subdomain = os.getenv('KINTONE_SUBDOMAIN')
guest_space_id = os.getenv('KINTONE_GUEST_SPACE_ID')
admin_user = os.getenv('KINTONE_ADMIN_USER')
admin_password = os.getenv('KINTONE_ADMIN_PASSWORD')

# 通常スペース
base_url_normal = f'https://{subdomain}.cybozu.com/k/v1'
# ゲストスペース
base_url_guest = f'https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1'

auth_string = base64.b64encode(f'{admin_user}:{admin_password}'.encode()).decode()
headers = {'X-Cybozu-Authorization': auth_string}

# 通常スペースのアプリ取得
print('=== 通常スペースのアプリ ===')
r = requests.get(f'{base_url_normal}/apps.json', headers=headers, params={'limit': 100}, timeout=30)
if r.status_code == 200:
    data = r.json()
    apps = data.get('apps', [])
    print(f'件数: {len(apps)}\n')
    for app in sorted(apps, key=lambda x: int(x.get('appId', 0))):
        app_id = app.get('appId', '')
        app_name = app.get('name', '')
        app_code = app.get('code', '')
        print(f'ID:{app_id:4s} | {app_name:40s} | code:{app_code}')
else:
    print(f'エラー: {r.status_code}')

print('\n=== ゲストスペースのアプリ ===')
r = requests.get(f'{base_url_guest}/apps.json', headers=headers, params={'limit': 100}, timeout=30)
if r.status_code == 200:
    data = r.json()
    apps = data.get('apps', [])
    print(f'件数: {len(apps)}\n')
    for app in sorted(apps, key=lambda x: int(x.get('appId', 0))):
        app_id = app.get('appId', '')
        app_name = app.get('name', '')
        app_code = app.get('code', '')
        print(f'ID:{app_id:4s} | {app_name:40s} | code:{app_code}')
else:
    print(f'エラー: {r.status_code} {r.text}')
