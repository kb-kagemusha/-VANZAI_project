#!/usr/bin/env python
"""
Kintoneアプリを新規作成し、正しいフィールド定義で設定する

目的:
- DROP_DOWNフィールドの問題を回避
- 全フィールドをSINGLE_LINE_TEXTまたは適切な型で作成
- DB→Kintone同期をスムーズに実行できる環境を構築

使用方法:
    python scripts/recreate_kintone_apps.py [app_name]
    python scripts/recreate_kintone_apps.py all
    
対応アプリ: workers, clients, sites, roles, project_types
"""
import os
import sys
from pathlib import Path
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from scripts.legacy.kintone.kintone_service import KintoneService, KintoneConfig

load_dotenv()

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")


# アプリ定義（正しいフィールドタイプで）
APP_TEMPLATES = {
    "workers": {
        "name": "workers_new",
        "token_env": "KINTONE_TOKEN_WORKERS",  # 既存トークンを再利用するか、新規生成が必要
        "description": "稼働者マスタ（DB→Kintone同期用）",
        "fields": {
            "worker_id": {
                "type": "SINGLE_LINE_TEXT",
                "code": "worker_id",
                "label": "worker_id",
                "noLabel": False,
                "required": False,
                "unique": True
            },
            "name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "name",
                "label": "name",
                "required": True
            },
            "email": {
                "type": "LINK",  # メールアドレス用
                "code": "email",
                "label": "email",
                "protocol": "MAIL",
                "required": False
            },
            "phone": {
                "type": "SINGLE_LINE_TEXT",
                "code": "phone",
                "label": "phone",
                "required": False
            },
            "is_active": {
                "type": "DROP_DOWN",  # これは選択肢が固定なのでDROP_DOWNでOK
                "code": "is_active",
                "label": "is_active",
                "required": False,
                "options": {
                    "有効": {"label": "有効", "index": "0"},
                    "無効": {"label": "無効", "index": "1"}
                },
                "defaultValue": "有効"
            },
            "notes": {
                "type": "MULTI_LINE_TEXT",
                "code": "notes",
                "label": "notes",
                "required": False
            }
        }
    },
    "clients": {
        "name": "clients_new",
        "token_env": "KINTONE_TOKEN_CLIENTS",
        "description": "クライアント（請求先）マスタ",
        "fields": {
            "client_id": {
                "type": "SINGLE_LINE_TEXT",
                "code": "client_id",
                "label": "client_id",
                "required": False,
                "unique": True
            },
            "code": {
                "type": "SINGLE_LINE_TEXT",
                "code": "code",
                "label": "code",
                "required": False
            },
            "name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "name",
                "label": "name",
                "required": True
            },
            "address": {
                "type": "MULTI_LINE_TEXT",
                "code": "address",
                "label": "address",
                "required": False
            },
            "contact_name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "contact_name",
                "label": "contact_name",
                "required": False
            },
            "contact_email": {
                "type": "LINK",
                "code": "contact_email",
                "label": "contact_email",
                "protocol": "MAIL",
                "required": False
            },
            "notes": {
                "type": "MULTI_LINE_TEXT",
                "code": "notes",
                "label": "notes",
                "required": False
            }
        }
    },
    "sites": {
        "name": "sites_new",
        "token_env": "KINTONE_TOKEN_SITES",
        "description": "現場マスタ",
        "fields": {
            "site_id": {
                "type": "SINGLE_LINE_TEXT",
                "code": "site_id",
                "label": "site_id",
                "required": False,
                "unique": True
            },
            "code": {
                "type": "SINGLE_LINE_TEXT",
                "code": "code",
                "label": "code",
                "required": False
            },
            "name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "name",
                "label": "name",
                "required": True
            },
            "address": {
                "type": "MULTI_LINE_TEXT",
                "code": "address",
                "label": "address",
                "required": False
            },
            "notes": {
                "type": "MULTI_LINE_TEXT",
                "code": "notes",
                "label": "notes",
                "required": False
            }
        }
    },
    "roles": {
        "name": "roles_new",
        "token_env": "KINTONE_TOKEN_ROLES",
        "description": "役割マスタ",
        "fields": {
            "role_id": {
                "type": "SINGLE_LINE_TEXT",
                "code": "role_id",
                "label": "role_id",
                "required": False,
                "unique": True
            },
            "code": {
                "type": "SINGLE_LINE_TEXT",
                "code": "code",
                "label": "code",
                "required": False
            },
            "name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "name",
                "label": "name",
                "required": True
            },
            "description": {
                "type": "MULTI_LINE_TEXT",
                "code": "description",
                "label": "description",
                "required": False
            }
        }
    },
    "project_types": {
        "name": "project_types_new",
        "token_env": "KINTONE_TOKEN_PROJECT_TYPES",
        "description": "案件種別マスタ",
        "fields": {
            "type_id": {
                "type": "SINGLE_LINE_TEXT",
                "code": "type_id",
                "label": "type_id",
                "required": False,
                "unique": True
            },
            "code": {
                "type": "SINGLE_LINE_TEXT",
                "code": "code",
                "label": "code",
                "required": False
            },
            "name": {
                "type": "SINGLE_LINE_TEXT",
                "code": "name",
                "label": "name",
                "required": True
            },
            "description": {
                "type": "MULTI_LINE_TEXT",
                "code": "description",
                "label": "description",
                "required": False
            }
        }
    }
}


def create_kintone_app_from_template(kintone_service: KintoneService, template: dict):
    """
    テンプレートからKintoneアプリを新規作成
    
    注意: この処理は以下の手順が必要
    1. アプリ作成（基本情報のみ）
    2. フィールド追加（プレビュー環境）
    3. アプリをデプロイ（本番環境に反映）
    4. APIトークン生成（手動またはAPI経由）
    """
    print(f"\n{'='*60}")
    print(f"アプリ作成: {template['name']}")
    print(f"{'='*60}")
    
    # ステップ1: アプリ作成
    print("\n[ステップ1] アプリ作成...")
    try:
        app_data = {
            "name": template['name'],
            "space": int(GUEST_SPACE_ID) if GUEST_SPACE_ID else None,
            "thread": "false"
        }
        
        # Kintone REST API: POST /k/v1/preview/app.json
        # しかし、KintoneServiceに実装されていない可能性があるため、
        # 直接requestsを使用する
        import requests
        
        url = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1/preview/app.json"
        headers = {
            "X-Cybozu-API-Token": os.getenv(template['token_env']),
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=app_data, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        app_id = result.get('app')
        print(f"✅ アプリ作成成功: app_id={app_id}")
        
        # ステップ2: フィールド追加
        print("\n[ステップ2] フィールド追加中...")
        
        # フィールド追加API: PUT /k/v1/preview/app/form/fields.json
        url_fields = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1/preview/app/form/fields.json"
        
        fields_payload = {
            "app": app_id,
            "properties": template['fields'],
            "revision": -1
        }
        
        response_fields = requests.put(url_fields, json=fields_payload, headers=headers, timeout=30)
        response_fields.raise_for_status()
        
        print(f"✅ フィールド追加成功: {len(template['fields'])} 件")
        
        # ステップ3: デプロイ
        print("\n[ステップ3] アプリをデプロイ中...")
        
        url_deploy = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1/preview/app/deploy.json"
        deploy_payload = {
            "apps": [{"app": app_id}],
            "revert": False
        }
        
        response_deploy = requests.post(url_deploy, json=deploy_payload, headers=headers, timeout=30)
        response_deploy.raise_for_status()
        
        print(f"✅ デプロイ成功")
        
        # デプロイ完了まで待機
        print("\n[ステップ4] デプロイ完了確認中...")
        time.sleep(3)
        
        print(f"\n{'='*60}")
        print(f"✅ アプリ作成完了")
        print(f"{'='*60}")
        print(f"アプリID: {app_id}")
        print(f"アプリ名: {template['name']}")
        print(f"URL: https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/show#record={app_id}")
        print(f"\n⚠️ 次の作業:")
        print(f"1. Kintone UIでアプリを開く")
        print(f"2. 「設定」→「API」からAPIトークンを生成")
        print(f"3. トークンを .env の {template['token_env']} に設定")
        print(f"4. または、環境変数 KINTONE_APP_{template['name'].upper()} に {app_id} を設定")
        
        return {"app_id": app_id, "name": template['name']}
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        if hasattr(e, 'response'):
            print(f"レスポンス: {e.response.text}")
        return None


def main():
    if len(sys.argv) < 2:
        print("使用方法: python scripts/recreate_kintone_apps.py [app_name]")
        print(f"対応アプリ: {', '.join(APP_TEMPLATES.keys())}, all")
        sys.exit(1)
    
    target = sys.argv[1].lower()
    
    print("=" * 60)
    print("Kintoneアプリ再作成")
    print("=" * 60)
    print(f"対象: {target}")
    
    # Kintoneサービス初期化
    config = KintoneConfig(
        subdomain=SUBDOMAIN,
        guest_space_id=GUEST_SPACE_ID,
        api_token=""  # アプリ作成では各アプリのトークンを個別に使用
    )
    
    kintone_service = KintoneService(config)
    
    # 対象アプリ決定
    if target == "all":
        targets = list(APP_TEMPLATES.keys())
    elif target in APP_TEMPLATES:
        targets = [target]
    else:
        print(f"❌ 不明なアプリ: {target}")
        sys.exit(1)
    
    # アプリ作成実行
    results = []
    for app_name in targets:
        template = APP_TEMPLATES[app_name]
        result = create_kintone_app_from_template(kintone_service, template)
        results.append(result)
        time.sleep(2)  # API制限対策
    
    # サマリ
    print("\n" + "=" * 60)
    print("✅ 全アプリ作成完了")
    print("=" * 60)
    for result in results:
        if result:
            print(f"  {result['name']:20s}: app_id={result['app_id']}")
    
    print("\n⚠️ 次のステップ:")
    print("1. 各アプリでAPIトークンを生成")
    print("2. .env に新しいアプリIDとトークンを設定")
    print("3. DB→Kintone同期を実行:")
    print("   python scripts/sync_db_to_kintone.py all")


if __name__ == "__main__":
    main()
