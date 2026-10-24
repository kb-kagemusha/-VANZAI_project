"""Kintone マスタデータ一括取込スクリプト

対象アプリ:
    - App 166: sites (現場マスタ)
    - App 163: roles (役割マスタ)
    - App 164: project_types (案件種別マスタ)

使用方法:
    python scripts/import_masters_from_kintone.py [--dry-run]

重複排除ルール:
    - sites:         site_id (ULID) が DB の id と一致 → スキップ、code が一致 → スキップ
    - roles:         role_id (ULID) が DB の id と一致 → スキップ、name が一致 → スキップ
    - project_types: type_id (PT:xxx) が DB の code と一致 → スキップ、name が一致 → スキップ
"""
import sys
import os
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import requests
from datetime import datetime
from sqlalchemy.orm import Session
from src.api.deps import SessionLocal
from src.models.master import Site, Role, ProjectType
from src.models.base import generate_ulid

DRY_RUN = "--dry-run" in sys.argv
_ULID_RE = re.compile(r"^[0-9A-Z]{26}$")

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_ID = os.getenv("KINTONE_GUEST_SPACE_ID", "3")


def _is_ulid(v: str) -> bool:
    return bool(v and _ULID_RE.match(str(v).strip().upper()))


def _kv(record: dict, field: str) -> str:
    entry = record.get(field, {})
    if isinstance(entry, dict):
        return str(entry.get("value") or "").strip()
    return str(entry or "").strip()


def fetch_all(token: str, app_id: int) -> list[dict]:
    """Kintone から全レコードを 500 件ずつ取得"""
    url = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_ID}/v1/records.json"
    headers = {"X-Cybozu-API-Token": token}
    records: list[dict] = []
    offset = 0
    while True:
        r = requests.get(
            url,
            headers=headers,
            params={"app": app_id, "query": f"limit 500 offset {offset}"},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json().get("records", [])
        records.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    return records


# ─────────────────────────────────────────────
# Sites (App 166)
# ─────────────────────────────────────────────

def import_sites(db: Session) -> dict:
    token = os.getenv("KINTONE_TOKEN_SITES")
    app_id = int(os.getenv("KINTONE_APP_SITES", "166"))

    print(f"\n[Sites] App {app_id} 取得中...")
    records = fetch_all(token, app_id)
    print(f"  Kintone: {len(records)} 件")

    # 既存データ
    existing_ids = {s.id for s in db.query(Site.id).all()}
    existing_codes = {s.code for s in db.query(Site.code).filter(Site.code.isnot(None)).all()}

    added = skipped = 0
    for rec in records:
        site_id = _kv(rec, "site_id")
        code = _kv(rec, "code") or None
        name = _kv(rec, "name")
        address = _kv(rec, "address") or None
        notes = _kv(rec, "notes") or None

        if not name:
            print(f"  SKIP name未設定: {rec}")
            skipped += 1
            continue

        # 重複チェック
        if _is_ulid(site_id) and site_id in existing_ids:
            skipped += 1
            continue
        if code and code in existing_codes:
            skipped += 1
            continue

        new_id = site_id if _is_ulid(site_id) else generate_ulid()
        site = Site(id=new_id, name=name, code=code, address=address, notes=notes)
        if not DRY_RUN:
            db.add(site)
        existing_ids.add(new_id)
        if code:
            existing_codes.add(code)
        added += 1

    if not DRY_RUN:
        db.flush()
    print(f"  追加: {added} 件 / スキップ: {skipped} 件")
    return {"added": added, "skipped": skipped}


# ─────────────────────────────────────────────
# Roles (App 163)
# ─────────────────────────────────────────────

def import_roles(db: Session) -> dict:
    token = os.getenv("KINTONE_TOKEN_ROLES")
    app_id = int(os.getenv("KINTONE_APP_ROLES", "163"))

    print(f"\n[Roles] App {app_id} 取得中...")
    records = fetch_all(token, app_id)
    print(f"  Kintone: {len(records)} 件")

    existing_ids = {r.id for r in db.query(Role.id).all()}
    existing_names = {r.name for r in db.query(Role.name).all()}

    added = skipped = 0
    for rec in records:
        role_id = _kv(rec, "role_id")
        name = _kv(rec, "name")
        description = _kv(rec, "description") or None

        if not name:
            skipped += 1
            continue

        if _is_ulid(role_id) and role_id in existing_ids:
            skipped += 1
            continue
        if name in existing_names:
            skipped += 1
            continue

        new_id = role_id if _is_ulid(role_id) else generate_ulid()
        role = Role(id=new_id, name=name, code=None, description=description)
        if not DRY_RUN:
            db.add(role)
        existing_ids.add(new_id)
        existing_names.add(name)
        added += 1

    if not DRY_RUN:
        db.flush()
    print(f"  追加: {added} 件 / スキップ: {skipped} 件")
    return {"added": added, "skipped": skipped}


# ─────────────────────────────────────────────
# ProjectTypes (App 164)
# ─────────────────────────────────────────────

def import_project_types(db: Session) -> dict:
    token = os.getenv("KINTONE_TOKEN_PROJECT_TYPES")
    app_id = int(os.getenv("KINTONE_APP_PROJECT_TYPES", "164"))

    print(f"\n[ProjectTypes] App {app_id} 取得中...")
    records = fetch_all(token, app_id)
    print(f"  Kintone: {len(records)} 件")

    existing_codes = {pt.code for pt in db.query(ProjectType.code).filter(ProjectType.code.isnot(None)).all()}
    existing_names = {pt.name for pt in db.query(ProjectType.name).all()}

    added = skipped = 0
    for rec in records:
        type_id = _kv(rec, "type_id")   # PT127 形式
        name = _kv(rec, "name")
        description = _kv(rec, "description") or None
        parent_major = _kv(rec, "parent_major") or None
        parent_middle = _kv(rec, "parent_middle") or None

        if not name:
            skipped += 1
            continue

        if type_id and type_id in existing_codes:
            skipped += 1
            continue
        if name in existing_names:
            skipped += 1
            continue

        pt = ProjectType(
            id=generate_ulid(),
            name=name,
            code=type_id if type_id else None,
            description=description,
        )
        if not DRY_RUN:
            db.add(pt)
        if type_id:
            existing_codes.add(type_id)
        existing_names.add(name)
        added += 1

    if not DRY_RUN:
        db.flush()
    print(f"  追加: {added} 件 / スキップ: {skipped} 件")
    return {"added": added, "skipped": skipped}


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"Kintone マスタデータ取込{'（DRY-RUN）' if DRY_RUN else ''}")
    print("=" * 60)

    db = SessionLocal()
    try:
        results = {}
        results["sites"] = import_sites(db)
        results["roles"] = import_roles(db)
        results["project_types"] = import_project_types(db)

        if not DRY_RUN:
            db.commit()
            print("\n✅ コミット完了")
        else:
            print("\n（dry-run: ロールバック）")
            db.rollback()

        print("\n=== 結果サマリー ===")
        total_added = 0
        for name, r in results.items():
            print(f"  {name:<20}: 追加 {r['added']:3} / スキップ {r['skipped']:3}")
            total_added += r["added"]
        print(f"  {'合計':<20}: 追加 {total_added:3}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
