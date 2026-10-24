import requests
from dotenv import load_dotenv
import os
import json

load_dotenv()

url = 'https://xtf5wpxp3gk2.cybozu.com/k/guest/3/v1/records.json'
headers = {'X-Cybozu-API-Token': os.getenv('KINTONE_TOKEN_WORKERS')}
params = {'app': '165'}

response = requests.get(url, headers=headers, params=params)
data = response.json()

if data.get('records'):
    record = data['records'][0]
    print('=' * 60)
    print('Kintone稼働者マスタのフィールド一覧')
    print('=' * 60)
    for k, v in record.items():
        if not k.startswith('$'):
            value = v.get('value', '') if isinstance(v, dict) else v
            print(f'{k}: {value}')
else:
    print('レコードなし')
