"""
Kintoneから登録済みデータを確認

使用方法:
    python scripts/check_kintone_data.py [アプリID]
    
    例: python scripts/check_kintone_data.py 165
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.services.kintone_service import KintoneService, KintoneConfig
import json

load_dotenv()

# コマンドライン引数
app_id = int(sys.argv[1]) if len(sys.argv) > 1 else 165
token_env_override = sys.argv[2] if len(sys.argv) > 2 else None

# アプリ名とトークンのマッピング
app_tokens = {
    165: "KINTONE_TOKEN_WORKERS",
    167: "KINTONE_TOKEN_CLIENTS",
    166: "KINTONE_TOKEN_SITES",
    163: "KINTONE_TOKEN_ROLES",
    164: "KINTONE_TOKEN_PROJECT_TYPES",
}

print(f"=" * 60)
print(f"Kintoneデータ確認 - アプリID: {app_id}")
print(f"=" * 60)

# 設定
config = KintoneConfig()
token_env = token_env_override or app_tokens.get(app_id)

if not token_env:
    print("❌ エラー: トークン環境変数が特定できません")
    print("使用方法: python scripts/check_kintone_data.py [アプリID] [TOKEN_ENV(任意)]")
    print("例: python scripts/check_kintone_data.py 165 KINTONE_TOKEN_WORKERS")
    sys.exit(1)

token = os.getenv(token_env)

if not token:
    print(f"❌ エラー: APIトークンが設定されていません（{token_env}）")
    sys.exit(1)

print(f"\nサブドメイン: {config.subdomain}")
print(f"ゲストスペースID: {config.guest_space_id}")
print(f"APIトークン: {token[:10]}...")

# Kintoneサービス初期化
service = KintoneService(config, api_token=token)

try:
    # レコード取得（最初の1件）
    print(f"\nレコード取得中...")
    records = service.get_records(app_id, query="limit 1")
    
    print(f"取得件数: {len(records)}")
    
    if records:
        print(f"\n" + "=" * 60)
        print("最初のレコードの内容:")
        print("=" * 60)
        
        record = records[0]
        
        # レコード番号
        print(f"\nレコード番号: {record.get('$id', {}).get('value', 'N/A')}")
        
        # 各フィールドを表示
        print(f"\nフィールド一覧:")
        for field_code, field_data in sorted(record.items()):
            # システムフィールド（$で始まる）はスキップ
            if field_code.startswith('$'):
                continue
            
            # 値を取得
            if isinstance(field_data, dict):
                value = field_data.get('value', '')
                field_type = field_data.get('type', 'unknown')
            else:
                value = field_data
                field_type = 'unknown'
            
            # 長い値は省略
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            
            print(f"  {field_code} ({field_type}): {value}")
        
        # JSON形式でも出力
        print(f"\n" + "=" * 60)
        print("JSON形式（最初の5フィールド）:")
        print("=" * 60)
        
        limited_record = {}
        count = 0
        for key, val in record.items():
            if not key.startswith('$') and count < 5:
                limited_record[key] = val
                count += 1
        
        print(json.dumps(limited_record, indent=2, ensure_ascii=False))
        
    else:
        print("\n⚠️ レコードが0件です")
        print("\n確認事項:")
        print("1. Kintoneアプリにデータが登録されているか")
        print("2. APIトークンに「閲覧」権限があるか")
    
except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
