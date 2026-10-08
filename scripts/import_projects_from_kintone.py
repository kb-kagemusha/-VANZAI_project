"""Kintone App 160 (案件) → DB 取込スクリプト

使用方法:
    python scripts/import_projects_from_kintone.py [--dry-run]

重複排除ルール:
    - project_id (ULID) が DB の id と一致 → スキップ
    - code が一致 → スキップ

FK 解決:
    - client_id  : DB に存在しない場合はスキップ（警告表示）
    - site_id    : DB に存在しない場合は NULL でインポート（警告表示）
    - project_type_id: DB に存在しない場合は NULL でインポート（警告表示）
"""
import sys
import os
import re
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import requests
from sqlalchemy.orm import Session
from src.api.deps import SessionLocal
from src.models.transaction import Project
from src.models.master import Client, Site, ProjectType
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


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def fetch_all(token: str, app_id: int) -> list[dict]:
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


def main():
    token = os.getenv("KINTONE_TOKEN_PROJECTS")
    app_id = int(os.getenv("KINTONE_APP_PROJECTS", "160"))

    print("=" * 60)
    print(f"Kintone → DB 案件取込{'（DRY-RUN）' if DRY_RUN else ''}")
    print("=" * 60)
    print(f"\n[Projects] App {app_id} 取得中...")
    records = fetch_all(token, app_id)
    print(f"  Kintone: {len(records)} 件")

    db: Session = SessionLocal()
    try:
        # 既存データのセット
        existing_ids = {p.id for p in db.query(Project.id).all()}
        existing_codes = {p.code for p in db.query(Project.code).filter(Project.code.isnot(None)).all()}

        # FK 解決用セット
        client_ids = {c.id for c in db.query(Client.id).filter(Client.deleted_at.is_(None)).all()}
        site_ids = {s.id for s in db.query(Site.id).filter(Site.deleted_at.is_(None)).all()}
        pt_ids = {pt.id for pt in db.query(ProjectType.id).filter(ProjectType.deleted_at.is_(None)).all()}

        added = skipped = 0
        warn_client = warn_site = warn_pt = 0

        for rec in records:
            project_id = _kv(rec, "project_id")
            name = _kv(rec, "name")
            client_id = _kv(rec, "client_id") or None
            site_id = _kv(rec, "site_id") or None
            pt_id = _kv(rec, "project_type_id") or None
            start_date = _parse_date(_kv(rec, "start_date"))
            end_date = _parse_date(_kv(rec, "end_date"))
            notes = _kv(rec, "notes") or None
            status = _kv(rec, "status") or "operating"

            if not name:
                skipped += 1
                continue

            # 重複チェック
            if _is_ulid(project_id) and project_id in existing_ids:
                skipped += 1
                continue

            # client_id は必須 FK
            if not client_id or client_id not in client_ids:
                print(f"  SKIP client_id未解決 [{client_id}]: {name}")
                warn_client += 1
                skipped += 1
                continue

            # site_id: 任意 FK
            resolved_site = site_id if site_id and site_id in site_ids else None
            if site_id and not resolved_site:
                print(f"  WARN site_id未解決 [{site_id}]: {name} → NULL にして継続")
                warn_site += 1

            # project_type_id: 任意 FK
            resolved_pt = pt_id if pt_id and pt_id in pt_ids else None
            if pt_id and not resolved_pt:
                warn_pt += 1

            new_id = project_id if _is_ulid(project_id) else generate_ulid()
            proj = Project(
                id=new_id,
                name=name,
                code=None,
                client_id=client_id,
                site_id=resolved_site,
                project_type_id=resolved_pt,
                start_date=start_date,
                end_date=end_date,
                notes=notes,
                is_active=(status not in {"closed", "cancelled", "canceled"}),
            )
            if not DRY_RUN:
                db.add(proj)
            existing_ids.add(new_id)
            added += 1

        if not DRY_RUN:
            db.commit()
            print("\n✅ コミット完了")
        else:
            db.rollback()
            print("\n（dry-run: ロールバック）")

        print(f"\n=== 結果 ===")
        print(f"  追加  : {added} 件")
        print(f"  スキップ: {skipped} 件")
        print(f"  警告: client未解決={warn_client}, site未解決={warn_site}, pt未解決={warn_pt}")

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
