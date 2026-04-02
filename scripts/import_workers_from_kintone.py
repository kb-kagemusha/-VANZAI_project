"""Kintone App 165 (稼働者マスタ) → DB 全件取込スクリプト

使用方法:
    python scripts/import_workers_from_kintone.py [--dry-run]

オプション:
    --dry-run   DBへの書き込みを行わず、取込内容を確認のみ（デフォルト: 書き込みあり）

前提:
    - .env に KINTONE_SUBDOMAIN, KINTONE_TOKEN_WORKERS, KINTONE_APP_WORKERS (省略時 165) が設定済み
    - 仮想環境が有効

重複排除ルール:
    1. Kintone の worker_id が DB の id (ULID 26文字) と一致 → スキップ
    2. Kintone の email が DB の email と一致 → スキップ
    3. 上記いずれにも該当しない → 新規作成 (ULID 生成)
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
from sqlalchemy.orm import Session
from src.api.deps import SessionLocal
from src.models.master import Worker
from src.models.base import generate_ulid

# ULID: 26文字の大文字英数字 (Crockford base32)
_ULID_RE = re.compile(r"^[0-9A-Z]{26}$")


def _is_ulid(value: str) -> bool:
    return bool(value and _ULID_RE.match(value.strip().upper()))


def _kv(record: dict, field: str) -> str:
    """Kintone レコードからフィールド値を文字列で取得"""
    entry = record.get(field, {})
    if isinstance(entry, dict):
        return str(entry.get("value") or "").strip()
    return str(entry or "").strip()


def _to_bool(value: str) -> bool:
    """'有効'/'無効'/True/False/1/0 を bool に変換"""
    if isinstance(value, bool):
        return value
    lower = str(value).lower().strip()
    return lower in {"有効", "true", "1", "yes"}


def fetch_all_workers(subdomain: str, guest_space_id: str, token: str, app_id: int) -> list[dict]:
    """Kintone から全レコードをページネーション取得"""
    if guest_space_id:
        base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    else:
        base_url = f"https://{subdomain}.cybozu.com/k/v1"

    url = f"{base_url}/records.json"
    headers = {"X-Cybozu-API-Token": token}
    all_records = []
    offset = 0
    limit = 500

    while True:
        params = {
            "app": str(app_id),
            "query": f"order by $id asc limit {limit} offset {offset}",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Kintone API エラー (HTTP {resp.status_code}): {resp.text}")
        records = resp.json().get("records", [])
        all_records.extend(records)
        if len(records) < limit:
            break
        offset += limit

    return all_records


def import_workers(dry_run: bool = False) -> None:
    subdomain = os.getenv("KINTONE_SUBDOMAIN", "")
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID", "")
    token = os.getenv("KINTONE_TOKEN_WORKERS", "")
    app_id = int(os.getenv("KINTONE_APP_WORKERS", "165"))

    if not subdomain or not token:
        print("❌ KINTONE_SUBDOMAIN または KINTONE_TOKEN_WORKERS が未設定です (.env を確認してください)")
        sys.exit(1)

    print("=" * 60)
    print("Kintone 稼働者マスタ → DB 取込")
    print(f"  サブドメイン : {subdomain}")
    print(f"  アプリID    : {app_id}")
    print(f"  モード      : {'dry-run（書き込み無し）' if dry_run else '本番（DB書き込みあり）'}")
    print("=" * 60)

    print("\n[1/3] Kintone からレコード取得中...")
    records = fetch_all_workers(subdomain, guest_space_id, token, app_id)
    print(f"  取得件数: {len(records)} 件")

    if not records:
        print("取得レコードが 0 件のため終了します。")
        return

    print("\n[2/3] DB との差分チェック...")
    db: Session = SessionLocal()
    try:
        existing_ids = {w.id for w in db.query(Worker.id).all()}
        existing_emails = {w.email.lower() for w in db.query(Worker.email).filter(Worker.email != None).all()}

        added = 0
        skipped_id = 0
        skipped_email = 0
        skipped_no_name = 0

        workers_to_add: list[Worker] = []

        for rec in records:
            kintone_worker_id = _kv(rec, "worker_id")
            last_name = _kv(rec, "last_name")
            first_name = _kv(rec, "first_name")
            name = " ".join(part for part in [last_name, first_name] if part).strip()
            # last_name/first_name が両方空の場合は name フィールドも試みる（フィールドコード変更対応）
            if not name:
                name = _kv(rec, "name")
            email = _kv(rec, "email") or None
            phone = _kv(rec, "phone") or None
            notes = _kv(rec, "memos") or _kv(rec, "notes") or None
            is_active = _to_bool(_kv(rec, "is_active") or "有効")
            introducer_supplier_id = _kv(rec, "introducer_supplier_id") or None

            if not name:
                skipped_no_name += 1
                print(f"  ⚠️  名前未設定のためスキップ (worker_id={kintone_worker_id!r})")
                continue

            # 重複チェック① : worker_id が ULID 形式 → DB の id と照合
            if _is_ulid(kintone_worker_id) and kintone_worker_id.upper() in existing_ids:
                skipped_id += 1
                continue

            # 重複チェック② : email で照合
            if email and email.lower() in existing_emails:
                skipped_email += 1
                continue

            new_id = kintone_worker_id.upper() if _is_ulid(kintone_worker_id) else generate_ulid()
            worker = Worker(
                id=new_id,
                name=name,
                email=email,
                phone=phone,
                notes=notes,
                is_active=is_active,
                introducer_supplier_id=introducer_supplier_id,
            )
            workers_to_add.append(worker)

            # dry-run でも既存セットを更新して重複防止
            existing_ids.add(new_id)
            if email:
                existing_emails.add(email.lower())

            added += 1
            print(f"  + [{new_id}] {name}  email={email or '(なし)'}")

        print(f"\n[3/3] {'取込予定' if dry_run else '取込'}サマリー")
        print(f"  取得    : {len(records)} 件")
        print(f"  新規追加: {added} 件")
        print(f"  スキップ (ID重複) : {skipped_id} 件")
        print(f"  スキップ (email重複): {skipped_email} 件")
        print(f"  スキップ (名前未設定): {skipped_no_name} 件")

        if dry_run:
            print("\n[dry-run] DB への書き込みはスキップしました。")
            return

        if workers_to_add:
            for w in workers_to_add:
                db.add(w)
            db.commit()
            print(f"\n✅ {added} 件を DB に登録しました。")
        else:
            print("\n新規追加対象が 0 件のため DB 書き込みはスキップしました。")

    except Exception as e:
        db.rollback()
        print(f"\n❌ エラーが発生しました: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    import_workers(dry_run=dry_run)
