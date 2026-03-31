"""
Kintone接続テスト

使用方法:
    python scripts/test_kintone_connection.py

前提:
    - .env ファイルに KINTONE_SUBDOMAIN 設定済み
    - 対象アプリ分のトークン/アプリIDが設定済み（例: KINTONE_TOKEN_WORKERS, KINTONE_APP_WORKERS）
    - pykintone-rest インストール済み
"""
import os
import sys
from pathlib import Path

# プロジェクトルート追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

print("=" * 60)
print("Kintone接続テスト")
print("=" * 60)

# 環境変数確認
subdomain = os.getenv("KINTONE_SUBDOMAIN")
guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
# アプリ別トークンを使用（稼働者マスタ）
api_token = os.getenv("KINTONE_TOKEN_WORKERS")
app_workers = os.getenv("KINTONE_APP_WORKERS")

print(f"\n[設定確認]")
print(f"サブドメイン: {subdomain}")
print(f"ゲストスペースID: {guest_space_id}")
print(f"APIトークン: {api_token[:10]}..." if api_token else "APIトークン: 未設定")
print(f"稼働者アプリID: {app_workers}")

if not subdomain or not api_token or not app_workers:
    print("\n❌ エラー: KINTONE_SUBDOMAIN / KINTONE_TOKEN_WORKERS / KINTONE_APP_WORKERS のいずれかが未設定です")
    print("\n対処方法:")
    print("1. .env ファイルを開く")
    print("2. 以下を設定:")
    print("   KINTONE_SUBDOMAIN=your-subdomain")
    print("   KINTONE_TOKEN_WORKERS=your-workers-token")
    print("   KINTONE_APP_WORKERS=123")
    sys.exit(1)

# pykintone インポート確認
try:
    import pykintone
    print(f"\n[pykintone インストール確認]")
    print(f"✅ pykintone インポート成功")
except ImportError:
    print("\n❌ エラー: pykintone がインストールされていません")
    print("\n対処方法:")
    print("  pip install pykintone")
    sys.exit(1)

# 接続テスト
print(f"\n[接続テスト]")

try:
    import requests
    
    # Kintone REST API URL（ゲストスペース対応）
    app_id = int(app_workers) if app_workers else 1
    
    if guest_space_id:
        url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1/records.json?app={app_id}&query=limit 5"
    else:
        url = f"https://{subdomain}.cybozu.com/k/v1/records.json?app={app_id}&query=limit 5"
    
    # ヘッダー
    headers = {
        "X-Cybozu-API-Token": api_token
    }
    
    print(f"アプリID {app_id} からレコード取得中...")
    print(f"URL: {url}")
    
    # リクエスト送信
    response = requests.get(url, headers=headers, timeout=10)
    
    # ステータスコード確認
    if response.status_code != 200:
        print(f"\n❌ HTTPエラー: {response.status_code}")
        print(f"レスポンス: {response.text}")
        sys.exit(1)
    
    # レコード取得
    data = response.json()
    records = data.get("records", [])
    
    print(f"✅ 接続成功！")
    print(f"取得件数: {len(records)}")
    
    # 最初のレコードを表示
    if records:
        print(f"\n[最初のレコードのフィールド一覧]")
        for key, value in records[0].items():
            # 値の型によって表示方法を変える
            if isinstance(value, dict):
                display_value = value.get("value", value)
            else:
                display_value = value
            
            # 長い値は省略
            if isinstance(display_value, str) and len(display_value) > 50:
                display_value = display_value[:50] + "..."
            
            print(f"  {key}: {display_value}")
    else:
        print("\n⚠️ レコードが0件です")
        print("対処方法:")
        print("  1. Kintoneでアプリを開く")
        print("  2. データが登録されているか確認")
        print("  3. APIトークンに「閲覧」権限があるか確認")
    
    print("\n" + "=" * 60)
    print("✅ テスト完了")
    print("=" * 60)
    
    print("\n次のステップ:")
    print("1. 他のアプリも同様にテスト")
    print("2. KintoneService.sync_workers() を実装")
    print("3. 実績取り込みスクリプトを実装")

except Exception as e:
    print(f"\n❌ エラー: {e}")
    print(f"\nエラータイプ: {type(e).__name__}")
    
    print("\n対処方法:")
    print("1. アプリIDが正しいか確認")
    print("2. APIトークンに適切な権限があるか確認")
    print("3. サブドメインが正しいか確認")
    print("4. インターネット接続を確認")
    
    import traceback
    print("\n詳細なエラー情報:")
    traceback.print_exc()
    
    sys.exit(1)
