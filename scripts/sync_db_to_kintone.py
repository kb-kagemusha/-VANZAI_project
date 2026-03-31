"""
ローカルDB → Kintone データ同期

使用方法:
    python scripts/sync_db_to_kintone.py [対象]
    
    対象: workers | clients | sites | roles | project_types | suppliers | all (デフォルト: all)
    
    例:
        python scripts/sync_db_to_kintone.py workers
        python scripts/sync_db_to_kintone.py suppliers
        python scripts/sync_db_to_kintone.py all

前提:
    - .env ファイル設定済み（KINTONE_SUBDOMAIN, KINTONE_GUEST_SPACE_ID, アプリ別トークン）
    - ローカルDBに同期対象データが存在
"""
import os
import sys
from pathlib import Path
import argparse

# プロジェクトルート追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.api.deps import SessionLocal
from src.models.master import Worker, Client, Site, Role, ProjectType, Supplier
from src.services.kintone_service import KintoneService, KintoneConfig
# from src.services.kintone_field_mappings import format_kintone_record  # マッピング不要

load_dotenv()

print("=" * 60)
print("DB→Kintone データ同期")
print("=" * 60)


def _extract_unique_flag(field_props: dict) -> bool | None:
    """kintoneのフィールド定義から「重複禁止」相当のフラグを推測する（ベストエフォート）。"""
    candidates = [
        "unique",
        "isUnique",
        "uniqueCheck",
        "duplicateCheck",
        "noDuplicate",
        "noDuplication",
        "checkDuplicate",
    ]
    for key in candidates:
        if key not in field_props:
            continue
        value = field_props.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in {"true", "false"}:
                return value.lower() == "true"
        if isinstance(value, dict):
            for sub_key in ["value", "enabled", "flag"]:
                sub = value.get(sub_key)
                if isinstance(sub, bool):
                    return sub
                if isinstance(sub, str) and sub.lower() in {"true", "false"}:
                    return sub.lower() == "true"
    return None


def validate_upsert_key(kintone_service: KintoneService, app_id: int, key_field: str) -> None:
    """UPSERT(updateKey)に必要な前提を、可能な範囲で事前チェックして注意喚起する。"""
    try:
        properties = kintone_service.get_form_fields(app_id)
    except Exception as e:
        print(f"⚠️ UPSERT前提チェックに失敗しました（app_id={app_id}）: {e}")
        print("   ※ 以降は実行を継続します。UPSERTで失敗した場合はキー項目の設定（重複禁止/型）を確認してください")
        return

    if key_field not in properties:
        print(f"⚠️ UPSERTキー項目 '{key_field}' がKintoneフォームに存在しません（app_id={app_id}）")
        print("   ※ UPSERTは失敗します。フィールドコードを一致させてください")
        return

    field_props = properties.get(key_field)
    if not isinstance(field_props, dict):
        return

    field_type = field_props.get("type")
    if isinstance(field_type, str) and field_type not in {"SINGLE_LINE_TEXT", "NUMBER"}:
        print(f"⚠️ UPSERTキー項目 '{key_field}' の型が想定外です: {field_type}")
        print("   ※ updateKey は通常 文字列(1行) または 数値 の重複禁止フィールドが必要です")

    unique_flag = _extract_unique_flag(field_props)
    if unique_flag is False:
        print(f"⚠️ UPSERTキー項目 '{key_field}' は重複禁止が無効の可能性があります")
        print("   ※ updateKey の要件によりUPSERTが失敗する場合があります。Kintone側で重複禁止を有効化してください")
    elif unique_flag is None:
        print(f"ℹ️ UPSERTキー項目 '{key_field}' の重複禁止設定は自動判定できませんでした")
        print("   ※ UPSERTで失敗した場合は、Kintone側で重複禁止が有効か確認してください")


def format_kintone_record(data: dict) -> dict:
    """
    DBデータをKintone形式に変換
    
    ✅ フィールドコード英語化済み: そのまま送信
    
    Args:
        data: DBレコードの辞書形式
    
    Returns:
        Kintone形式のレコード {"field": {"value": "val"}, ...}
    """
    kintone_record = {}
    for key, value in data.items():
        # None値は空文字列に変換
        if value is None:
            value = ""
        
        # bool値を文字列に変換
        if isinstance(value, bool):
            value = "有効" if value else "無効"
        
        # 日付・日時型を文字列に変換
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        
        kintone_record[key] = {"value": str(value)}
    
    return kintone_record


def sync_workers(db, kintone_service, app_id: int):
    """稼働者マスタを同期"""
    print(f"\n[稼働者マスタ同期]")
    print(f"アプリID: {app_id}")
    
    # DBから取得（deleted_atがNull=有効）
    workers = db.query(Worker).filter(Worker.deleted_at == None).all()
    print(f"DB件数: {len(workers)}")
    
    if not workers:
        print("⚠️ DBにデータがありません")
        return
    
    mode = os.getenv("KINTONE_SYNC_MODE", "upsert")

    try:
        if mode == "add":
            records = []
            for worker in workers:
                record = format_kintone_record({
                    "worker_id": worker.id,
                    "name": worker.name,
                    "email": worker.email,
                    "phone": worker.phone,
                    "notes": worker.notes,
                    "is_active": worker.is_active,
                    "introducer_supplier_id": worker.introducer_supplier_id,
                })
                records.append(record)

            result = kintone_service.add_records(app_id, records)
            print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
            return result

        # upsert（デフォルト）
        upsert_records = []
        for worker in workers:
            record = format_kintone_record({
                "worker_id": worker.id,
                "name": worker.name,
                "email": worker.email,
                "phone": worker.phone,
                "notes": worker.notes,
                "is_active": worker.is_active,
                "introducer_supplier_id": worker.introducer_supplier_id,
            })
            upsert_records.append({
                "updateKey": {"field": "worker_id", "value": str(worker.id)},
                "record": record,
            })

        result = kintone_service.upsert_records(app_id, upsert_records)
        print(f"✅ 同期成功: {len(result.get('records', []))} 件UPSERT")
        return result
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def sync_clients(db, kintone_service, app_id: int):
    """クライアントマスタを同期"""
    print(f"\n[クライアントマスタ同期]")
    print(f"アプリID: {app_id}")
    
    clients = db.query(Client).filter(Client.deleted_at == None).all()
    print(f"DB件数: {len(clients)}")
    
    if not clients:
        print("⚠️ DBにデータがありません")
        return
    
    mode = os.getenv("KINTONE_SYNC_MODE", "upsert")

    try:
        if mode == "add":
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
            result = kintone_service.add_records(app_id, records)
            print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
            return result

        upsert_records = []
        for client in clients:
            record = format_kintone_record({
                "client_id": client.id,
                "name": client.name,
                "code": client.code or "",
                "address": client.address or "",
                "contact_email": client.contact_email or "",
                "notes": client.notes or "",
            })
            upsert_records.append({
                "updateKey": {"field": "client_id", "value": str(client.id)},
                "record": record,
            })

        result = kintone_service.upsert_records(app_id, upsert_records)
        print(f"✅ 同期成功: {len(result.get('records', []))} 件UPSERT")
        return result
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def sync_sites(db, kintone_service, app_id: int):
    """現場マスタを同期"""
    print(f"\n[現場マスタ同期]")
    print(f"アプリID: {app_id}")
    
    sites = db.query(Site).filter(Site.deleted_at == None).all()
    print(f"DB件数: {len(sites)}")
    
    if not sites:
        print("⚠️ DBにデータがありません")
        return
    
    mode = os.getenv("KINTONE_SYNC_MODE", "upsert")

    try:
        if mode == "add":
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
            result = kintone_service.add_records(app_id, records)
            print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
            return result

        upsert_records = []
        for site in sites:
            record = format_kintone_record({
                "site_id": site.id,
                "name": site.name,
                "code": site.code,
                "address": site.address,
                "notes": site.notes,
            })
            upsert_records.append({
                "updateKey": {"field": "site_id", "value": str(site.id)},
                "record": record,
            })

        result = kintone_service.upsert_records(app_id, upsert_records)
        print(f"✅ 同期成功: {len(result.get('records', []))} 件UPSERT")
        return result
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def sync_roles(db, kintone_service, app_id: int):
    """役割マスタを同期"""
    print(f"\n[役割マスタ同期]")
    print(f"アプリID: {app_id}")
    
    roles = db.query(Role).filter(Role.deleted_at == None).all()
    print(f"DB件数: {len(roles)}")
    
    if not roles:
        print("⚠️ DBにデータがありません")
        return
    
    mode = os.getenv("KINTONE_SYNC_MODE", "upsert")

    try:
        if mode == "add":
            records = []
            for role in roles:
                record = format_kintone_record({
                    "role_id": role.id,
                    "name": role.name,
                    "description": role.description,
                })
                records.append(record)
            result = kintone_service.add_records(app_id, records)
            print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
            return result

        upsert_records = []
        for role in roles:
            record = format_kintone_record({
                "role_id": role.id,
                "name": role.name,
                "description": role.description,
            })
            upsert_records.append({
                "updateKey": {"field": "role_id", "value": str(role.id)},
                "record": record,
            })

        result = kintone_service.upsert_records(app_id, upsert_records)
        print(f"✅ 同期成功: {len(result.get('records', []))} 件UPSERT")
        return result
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def sync_project_types(db, kintone_service, app_id: int):
    """案件種別マスタを同期"""
    print(f"\n[案件種別マスタ同期]")
    print(f"アプリID: {app_id}")
    
    project_types = db.query(ProjectType).filter(ProjectType.deleted_at == None).all()
    print(f"DB件数: {len(project_types)}")
    
    if not project_types:
        print("⚠️ DBにデータがありません")
        return
    
    mode = os.getenv("KINTONE_SYNC_MODE", "upsert")

    records = []
    skipped = 0
    for pt in project_types:
        # Kintone側type_idが選択肢の場合はコード（例: PT01）を優先
        type_id_value = pt.code or pt.id
        if pt.code and not pt.code.startswith("PT"):
            skipped += 1
            continue

        record = format_kintone_record({
            "type_id": type_id_value,
            "name": pt.name,
            "description": pt.description,
        })
        records.append((type_id_value, record))

    try:
        if not records:
            print("⚠️ 同期対象がありません（type_idの形式を確認してください）")
            return None

        if mode == "add":
            add_records = [r for _, r in records]
            result = kintone_service.add_records(app_id, add_records)
            print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加 (スキップ: {skipped})")
            return result

        upsert_records = []
        for type_id_value, record in records:
            upsert_records.append({
                "updateKey": {"field": "type_id", "value": str(type_id_value)},
                "record": record,
            })

        result = kintone_service.upsert_records(app_id, upsert_records)
        print(f"✅ 同期成功: {len(result.get('records', []))} 件UPSERT (スキップ: {skipped})")
        return result
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def sync_suppliers(db, kintone_service, app_id: int):
    """紹介者（下請け）マスタを同期"""
    print(f"\n[紹介者マスタ同期]")
    print(f"アプリID: {app_id}")
    
    suppliers = db.query(Supplier).filter(Supplier.deleted_at == None).all()
    print(f"DB件数: {len(suppliers)}")
    
    if not suppliers:
        print("⚠️ DBにデータがありません")
        return
    
    mode = os.getenv("KINTONE_SYNC_MODE", "upsert")

    try:
        if mode == "add":
            records = []
            for supplier in suppliers:
                record = format_kintone_record({
                    "supplier_id": supplier.id,
                    "name": supplier.name,
                    "contact_email": supplier.contact_email or "",
                    "contact_phone": supplier.contact_phone or "",
                    "payout_terms_days": supplier.payout_terms_days,
                    "default_daily_price": supplier.default_daily_price,
                    "is_active": supplier.is_active,
                    "notes": supplier.notes or "",
                })
                records.append(record)

            result = kintone_service.add_records(app_id, records)
            print(f"✅ 同期成功: {len(result.get('ids', []))} 件追加")
            return result

        upsert_records = []
        for supplier in suppliers:
            record = format_kintone_record({
                "name": supplier.name,
                "contact_email": supplier.contact_email or "",
                "contact_phone": supplier.contact_phone or "",
                "payout_terms_days": supplier.payout_terms_days,
                "default_daily_price": supplier.default_daily_price,
                "is_active": supplier.is_active,
                "notes": supplier.notes or "",
            })
            upsert_records.append({
                "updateKey": {"field": "supplier_id", "value": str(supplier.id)},
                "record": record,
            })

        result = kintone_service.upsert_records(app_id, upsert_records)
        print(f"✅ 同期成功: {len(result.get('records', []))} 件UPSERT")
        return result
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="DB→Kintone マスタ同期")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["workers", "clients", "sites", "roles", "project_types", "suppliers", "all"],
        help="同期対象（デフォルト: all）",
    )
    parser.add_argument(
        "--mode",
        default="upsert",
        choices=["upsert", "add"],
        help="同期モード（デフォルト: upsert）。upsertは二重化防止（更新/追加）",
    )
    args = parser.parse_args()
    target = args.target
    mode = args.mode
    os.environ["KINTONE_SYNC_MODE"] = mode
    
    print(f"\n同期対象: {target}")
    print(f"同期モード: {mode}")
    
    # Kintoneサービス初期化
    config = KintoneConfig()
    
    # 各マスタの同期マップ
    sync_map = {
        "workers": {
            "token_env": "KINTONE_TOKEN_WORKERS",
            "app_env": "KINTONE_APP_WORKERS",
            "key_field": "worker_id",
            "func": sync_workers
        },
        "clients": {
            "token_env": "KINTONE_TOKEN_CLIENTS",
            "app_env": "KINTONE_APP_CLIENTS",
            "key_field": "client_id",
            "func": sync_clients
        },
        "sites": {
            "token_env": "KINTONE_TOKEN_SITES",
            "app_env": "KINTONE_APP_SITES",
            "key_field": "site_id",
            "func": sync_sites
        },
        "roles": {
            "token_env": "KINTONE_TOKEN_ROLES",
            "app_env": "KINTONE_APP_ROLES",
            "key_field": "role_id",
            "func": sync_roles
        },
        "project_types": {
            "token_env": "KINTONE_TOKEN_PROJECT_TYPES",
            "app_env": "KINTONE_APP_PROJECT_TYPES",
            "key_field": "type_id",
            "func": sync_project_types
        },
        "suppliers": {
            "token_env": "KINTONE_TOKEN_SUPPLIERS",
            "app_env": "KINTONE_APP_SUPPLIERS",
            "key_field": "supplier_id",
            "func": sync_suppliers
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
            print(f"指定可能な対象: {', '.join(sync_map.keys())}, all")
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
            
            # Kintoneサービス初期化（アプリ別トークン）
            kintone_service = KintoneService(config, api_token=api_token)

            if mode == "upsert":
                key_field = sync_info.get("key_field")
                if isinstance(key_field, str) and key_field:
                    validate_upsert_key(kintone_service, app_id, key_field)
            
            # 同期実行
            result = sync_info["func"](db, kintone_service, app_id)
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
