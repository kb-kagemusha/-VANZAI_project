#!/usr/bin/env python
"""
DB→Kintone同期（動的選択肢追加対応版）

ドロップダウンフィールドの選択肢を動的に追加してからレコードを投入する

使用方法:
    python scripts/sync_db_to_kintone_smart.py [対象]
    
    対象: workers | clients | sites | roles | project_types | all
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.api.deps import SessionLocal
from src.models.master import Worker, Client, Site, Role, ProjectType
from scripts.legacy.kintone.kintone_service import KintoneService, KintoneConfig
import requests

load_dotenv()

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"


def add_dropdown_options(app_id: int, field_code: str, values: List[str], api_token: str):
    """
    ドロップダウンフィールドに選択肢を追加
    
    既存の選択肢と重複しない値だけを追加する
    """
    print(f"  [{field_code}] 選択肢を追加中...")
    
    try:
        # 現在のフィールド定義を取得
        url_fields = f"{BASE_URL}/app/form/fields.json"
        headers = {"X-Cybozu-API-Token": api_token}
        response = requests.get(url_fields, headers=headers, params={"app": app_id}, timeout=30)
        response.raise_for_status()
        
        fields = response.json().get("properties", {})
        field = fields.get(field_code)
        
        if not field:
            print(f"    ⚠️ フィールド {field_code} が見つかりません")
            return False
        
        field_type = field.get("type")
        if field_type not in ["DROP_DOWN", "RADIO_BUTTON"]:
            print(f"    ℹ️ {field_code} は {field_type} なので選択肢追加不要")
            return True
        
        # 既存の選択肢を取得
        existing_options = field.get("options", {})
        existing_values = set(existing_options.keys())
        
        # 追加が必要な選択肢を抽出
        new_values = [v for v in values if v and v not in existing_values and v != "__dummy__"]
        
        if not new_values:
            print(f"    ✅ 既に全ての選択肢があります")
            return True
        
        # 新しい選択肢を追加
        updated_options = dict(existing_options)
        next_index = len(existing_options)
        
        for value in new_values:
            updated_options[value] = {
                "label": value,
                "index": str(next_index)
            }
            next_index += 1
        
        # フィールド更新（プレビュー）
        url_update = f"{BASE_URL}/preview/app/form/fields.json"
        headers_update = {
            "X-Cybozu-API-Token": api_token,
            "Content-Type": "application/json"
        }
        
        payload = {
            "app": app_id,
            "properties": {
                field_code: {
                    "type": field_type,
                    "code": field_code,
                    "label": field.get("label"),
                    "options": updated_options
                }
            },
            "revision": -1
        }
        
        response_update = requests.put(url_update, json=payload, headers=headers_update, timeout=30)
        response_update.raise_for_status()
        
        # デプロイ
        url_deploy = f"{BASE_URL}/preview/app/deploy.json"
        deploy_payload = {
            "apps": [{"app": app_id}],
            "revert": False
        }
        
        response_deploy = requests.post(url_deploy, json=deploy_payload, headers=headers_update, timeout=30)
        response_deploy.raise_for_status()
        
        print(f"    ✅ {len(new_values)} 件の選択肢を追加しました")
        time.sleep(2)  # デプロイ完了待ち
        
        return True
        
    except Exception as e:
        print(f"    ❌ エラー: {e}")
        if hasattr(e, 'response'):
            print(f"    レスポンス: {e.response.text}")
        return False


def format_kintone_record(data: dict) -> dict:
    """DBデータをKintone形式に変換"""
    kintone_record = {}
    for key, value in data.items():
        if value is None:
            value = ""
        if isinstance(value, bool):
            value = "有効" if value else "無効"
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        kintone_record[key] = {"value": str(value)}
    return kintone_record


def sync_workers_smart(db, app_id: int, api_token: str):
    """稼働者マスタを同期（動的選択肢追加）"""
    print(f"\n[稼働者マスタ同期（スマート版）]")
    print(f"アプリID: {app_id}")
    
    # DBから取得
    workers = db.query(Worker).filter(Worker.deleted_at == None).all()
    print(f"DB件数: {len(workers)}")
    
    if not workers:
        print("⚠️ DBにデータがありません")
        return False
    
    # 選択肢に追加する値を収集
    worker_ids = [w.id for w in workers]
    names = [w.name for w in workers]
    phones = [w.phone for w in workers if w.phone]
    
    # 選択肢を動的追加
    print("\n選択肢を動的追加中...")
    add_dropdown_options(app_id, "worker_id", worker_ids, api_token)
    add_dropdown_options(app_id, "name", names, api_token)
    add_dropdown_options(app_id, "phone", phones, api_token)
    
    # レコード作成
    print("\nレコードを作成中...")
    kintone_service = KintoneService(
        KintoneConfig(SUBDOMAIN, GUEST_SPACE_ID, ""),
        api_token=api_token
    )
    
    records = []
    for worker in workers:
        record = format_kintone_record({
            "worker_id": worker.id,
            "name": worker.name,
            "email": worker.email,
            "phone": worker.phone,
            "notes": worker.notes,
            "is_active": worker.is_active,
        })
        records.append(record)
    
    try:
        result = kintone_service.add_records(app_id, records)
        print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
        return True
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def sync_clients_smart(db, app_id: int, api_token: str):
    """クライアントマスタを同期（動的選択肢追加）"""
    print(f"\n[クライアントマスタ同期（スマート版）]")
    print(f"アプリID: {app_id}")
    
    clients = db.query(Client).filter(Client.deleted_at == None).all()
    print(f"DB件数: {len(clients)}")
    
    if not clients:
        print("⚠️ DBにデータがありません")
        return False
    
    # 選択肢に追加する値を収集
    client_ids = [c.id for c in clients]
    names = [c.name for c in clients]
    codes = [c.code for c in clients if c.code]
    addresses = [c.address for c in clients if c.address]  # 追加
    
    # 選択肢を動的追加
    print("\n選択肢を動的追加中...")
    add_dropdown_options(app_id, "client_id", client_ids, api_token)
    add_dropdown_options(app_id, "name", names, api_token)
    add_dropdown_options(app_id, "code", codes, api_token)
    add_dropdown_options(app_id, "address", addresses, api_token)  # 追加
    
    # レコード作成
    print("\nレコードを作成中...")
    kintone_service = KintoneService(
        KintoneConfig(SUBDOMAIN, GUEST_SPACE_ID, ""),
        api_token=api_token
    )
    
    records = []
    for client in clients:
        record = format_kintone_record({
            "client_id": client.id,
            "name": client.name,
            "code": client.code or "",
            "address": client.address or "",
            "contact_email": client.contact_email or "",
            "notes": client.notes or "",
        })
        records.append(record)
    
    try:
        result = kintone_service.add_records(app_id, records)
        print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
        return True
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def sync_sites_smart(db, app_id: int, api_token: str):
    """現場マスタを同期（動的選択肢追加）"""
    print(f"\n[現場マスタ同期（スマート版）]")
    print(f"アプリID: {app_id}")
    
    sites = db.query(Site).filter(Site.deleted_at == None).all()
    print(f"DB件数: {len(sites)}")
    
    if not sites:
        print("⚠️ DBにデータがありません")
        return False
    
    # 選択肢を動的追加
    site_ids = [s.id for s in sites]
    names = [s.name for s in sites]
    codes = [s.code for s in sites if s.code]
    addresses = [s.address for s in sites if s.address]  # 追加
    
    print("\n選択肢を動的追加中...")
    add_dropdown_options(app_id, "site_id", site_ids, api_token)
    add_dropdown_options(app_id, "name", names, api_token)
    add_dropdown_options(app_id, "code", codes, api_token)
    add_dropdown_options(app_id, "address", addresses, api_token)  # 追加
    
    # レコード作成
    print("\nレコードを作成中...")
    kintone_service = KintoneService(
        KintoneConfig(SUBDOMAIN, GUEST_SPACE_ID, ""),
        api_token=api_token
    )
    
    records = []
    for site in sites:
        record = format_kintone_record({
            "site_id": site.id,
            "name": site.name,
            "code": site.code,
            "address": site.address,
            "notes": site.notes,
        })
        records.append(record)
    
    try:
        result = kintone_service.add_records(app_id, records)
        print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
        return True
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def sync_roles_smart(db, app_id: int, api_token: str):
    """役割マスタを同期（動的選択肢追加）"""
    print(f"\n[役割マスタ同期（スマート版）]")
    print(f"アプリID: {app_id}")
    
    roles = db.query(Role).filter(Role.deleted_at == None).all()
    print(f"DB件数: {len(roles)}")
    
    if not roles:
        print("⚠️ DBにデータがありません")
        return False
    
    # 選択肢を動的追加
    role_ids = [r.id for r in roles]
    names = [r.name for r in roles]
    
    print("\n選択肢を動的追加中...")
    add_dropdown_options(app_id, "role_id", role_ids, api_token)
    add_dropdown_options(app_id, "name", names, api_token)
    
    # レコード作成
    print("\nレコードを作成中...")
    kintone_service = KintoneService(
        KintoneConfig(SUBDOMAIN, GUEST_SPACE_ID, ""),
        api_token=api_token
    )
    
    records = []
    for role in roles:
        record = format_kintone_record({
            "role_id": role.id,
            "name": role.name,
            "description": role.description,
        })
        records.append(record)
    
    try:
        result = kintone_service.add_records(app_id, records)
        print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
        return True
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def sync_project_types_smart(db, app_id: int, api_token: str):
    """案件種別マスタを同期（動的選択肢追加）"""
    print(f"\n[案件種別マスタ同期（スマート版）]")
    print(f"アプリID: {app_id}")
    
    ptypes = db.query(ProjectType).filter(ProjectType.deleted_at == None).all()
    print(f"DB件数: {len(ptypes)}")
    
    if not ptypes:
        print("⚠️ DBにデータがありません")
        return False
    
    # 選択肢を動的追加
    type_ids = [p.id for p in ptypes]
    names = [p.name for p in ptypes]
    
    print("\n選択肢を動的追加中...")
    add_dropdown_options(app_id, "project_type_id", type_ids, api_token)
    add_dropdown_options(app_id, "name", names, api_token)
    
    # レコード作成
    print("\nレコードを作成中...")
    kintone_service = KintoneService(
        KintoneConfig(SUBDOMAIN, GUEST_SPACE_ID, ""),
        api_token=api_token
    )
    
    records = []
    for ptype in ptypes:
        record = format_kintone_record({
            "project_type_id": ptype.id,
            "name": ptype.name,
            "description": ptype.description,
        })
        records.append(record)
    
    try:
        result = kintone_service.add_records(app_id, records)
        print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
        return True
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("使用方法: python scripts/sync_db_to_kintone_smart.py [対象]")
        print("対象: workers | clients | sites | roles | project_types | all")
        sys.exit(1)
    
    target = sys.argv[1].lower()
    
    print("=" * 60)
    print("DB→Kintone データ同期（スマート版）")
    print("=" * 60)
    print(f"\n同期対象: {target}\n")
    
    # 同期設定
    sync_map = {
        "workers": {
            "token_env": "KINTONE_TOKEN_WORKERS",
            "app_env": "KINTONE_APP_WORKERS",
            "func": sync_workers_smart
        },
        "clients": {
            "token_env": "KINTONE_TOKEN_CLIENTS",
            "app_env": "KINTONE_APP_CLIENTS",
            "func": sync_clients_smart
        },
        "sites": {
            "token_env": "KINTONE_TOKEN_SITES",
            "app_env": "KINTONE_APP_SITES",
            "func": sync_sites_smart
        },
        "roles": {
            "token_env": "KINTONE_TOKEN_ROLES",
            "app_env": "KINTONE_APP_ROLES",
            "func": sync_roles_smart
        },
        "project_types": {
            "token_env": "KINTONE_TOKEN_PROJECT_TYPES",
            "app_env": "KINTONE_APP_PROJECT_TYPES",
            "func": sync_project_types_smart
        }
    }
    
    # DBセッション
    db = SessionLocal()
    
    try:
        # 対象を決定
        if target == "all":
            targets = list(sync_map.keys())
        elif target in sync_map:
            targets = [target]
        else:
            print(f"❌ 不明な対象: {target}")
            sys.exit(1)
        
        # 同期実行
        results = {}
        for t in targets:
            sync_info = sync_map[t]
            
            # APIトークン取得
            api_token = os.getenv(sync_info["token_env"])
            if not api_token:
                print(f"\n⚠️ {t}: APIトークンが設定されていません（{sync_info['token_env']}）")
                continue
            
            # アプリID取得
            app_id = int(os.getenv(sync_info["app_env"], "0"))
            if not app_id:
                print(f"\n⚠️ {t}: アプリIDが設定されていません（{sync_info['app_env']}）")
                continue
            
            # 同期実行
            result = sync_info["func"](db, app_id, api_token)
            results[t] = result
        
        print("\n" + "=" * 60)
        print("✅ 同期処理完了")
        print("=" * 60)
        
        # サマリ表示
        print("\n[サマリ]")
        for t, result in results.items():
            if result:
                print(f"  {t}: ✅ 成功")
            else:
                print(f"  {t}: ❌ スキップまたはエラー")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
