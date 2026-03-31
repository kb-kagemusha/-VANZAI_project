#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次締め処理の簡易テストスクリプト
Task 10: Monthly closing test
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import requests
import io

# UTF-8出力を確保
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# API URL
BASE_URL = "http://localhost:8000"

def test_soft_close():
    """ソフト締め処理をテスト"""
    url = f"{BASE_URL}/api/closing/soft"
    data = {
        "project_id": "01KG1E59K7177GH432H0GM6WQN",  # ULIDを使用
        "period_key": "202601",
        "actor": "test_user",
        "reason": "テスト締め処理"
    }
    
    response = requests.post(url, json=data)
    print(f"✅ Soft Close: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  - 締め状態: {result.get('status')}")
        print(f"  - 期間: {result.get('period_key')}")
    else:
        print(f"  ❌ Error: {response.text[:200]}")
    return response.status_code == 200

def test_hard_close():
    """ハード締め処理をテスト"""
    url = f"{BASE_URL}/api/closing/hard"
    data = {
        "project_id": "01KG1E59K7177GH432H0GM6WQN",  # ULIDを使用
        "period_key": "202601",
        "actor": "test_user",
        "approver": "test_approver",
        "reason": "テスト締め処理（確定）"
    }
    
    response = requests.post(url, json=data)
    print(f"✅ Hard Close: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  - 締め状態: {result.get('status')}")
        print(f"  - 期間: {result.get('period_key')}")
    else:
        print(f"  ❌ Error: {response.text[:200]}")
    return response.status_code == 200

if __name__ == "__main__":
    print("=== 月次締め処理テスト ===\n")
    
    # APIサーバー確認
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"✅ API Server: {response.status_code}\n")
    except Exception as e:
        print(f"❌ API Server is not running: {e}")
        sys.exit(1)
    
    # 1. ソフト締めテスト
    if test_soft_close():
        print("  → ソフト締め成功\n")
    else:
        print("  → ソフト締め失敗\n")
    
    # 2. ハード締めテスト
    if test_hard_close():
        print("  → ハード締め成功\n")
    else:
        print("  → ハード締め失敗\n")
    
    print("✅ テスト完了")
