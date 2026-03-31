"""下請け（紹介者）を workers → suppliers へ移行

安全のため、このスクリプトはデフォルトで dry-run です。

使用方法:
    python scripts/migrate_introducers_to_suppliers.py            # dry-run
    python scripts/migrate_introducers_to_suppliers.py --commit   # 実移行

前提:
    - alembic upgrade head で suppliers テーブルが作成済み
    - workers.introducer_worker_id に紹介者が登録されている（旧方式・後方互換）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import select

from src.api.deps import SessionLocal
from src.models.master import Supplier, Worker
from src.services.audit import AuditService


load_dotenv()


def identify_introducers(db) -> list[Worker]:
    """紹介者として参照されている worker を抽出する。"""
    stmt = (
        select(Worker)
        .where(
            Worker.id.in_(
                select(Worker.introducer_worker_id)
                .where(Worker.introducer_worker_id != None)
                .distinct()
            )
        )
        .where(Worker.deleted_at == None)
    )
    return db.execute(stmt).scalars().all()


def find_existing_supplier(db, introducer_worker: Worker) -> Supplier | None:
    """既存 supplier を探す。

優先順位:
1) notes に移行元 worker_id が記録されている
2) name が一致（従来互換）
"""
    marker = f"移行元worker_id: {introducer_worker.id}"
    supplier = (
        db.query(Supplier)
        .filter(Supplier.deleted_at == None)
        .filter(Supplier.notes != None)
        .filter(Supplier.notes.contains(marker))
        .first()
    )
    if supplier:
        return supplier

    return (
        db.query(Supplier)
        .filter(Supplier.deleted_at == None)
        .filter(Supplier.name == introducer_worker.name)
        .first()
    )


def migrate_to_suppliers(db, introducers: list[Worker], *, dry_run: bool) -> dict:
    result = {
        "created_suppliers": 0,
        "linked_workers": 0,
        "already_linked_workers": 0,
        "conflict_workers": 0,
        "used_existing_suppliers": 0,
    }

    for introducer in introducers:
        print(f"\n[{introducer.id}] {introducer.name}")

        supplier = find_existing_supplier(db, introducer)
        if supplier:
            print(f"  ✅ 既存supplierを使用: '{supplier.name}' ({supplier.id})")
            result["used_existing_suppliers"] += 1
        else:
            supplier = Supplier(
                name=introducer.name,
                contact_email=introducer.email,
                contact_phone=introducer.phone,
                payout_terms_days=70,
                default_daily_price=None,
                is_active=introducer.is_active,
                notes=f"移行元worker_id: {introducer.id}\n{introducer.notes or ''}",
            )
            if dry_run:
                print(f"  [DRY RUN] Supplier作成予定: {supplier.name}")
            else:
                db.add(supplier)
                db.flush()
                print(f"  ✅ Supplier作成: {supplier.name} ({supplier.id})")
            result["created_suppliers"] += 1

        referencing_workers = (
            db.query(Worker)
            .filter(Worker.deleted_at == None)
            .filter(Worker.introducer_worker_id == introducer.id)
            .all()
        )
        if not referencing_workers:
            print("  ⚠️ 紹介者として参照しているworkerが見つかりません")
            continue

        for worker in referencing_workers:
            if worker.introducer_supplier_id:
                if worker.introducer_supplier_id == supplier.id:
                    print(f"    ⏭️ 既に紐付け済み: {worker.name}")
                    result["already_linked_workers"] += 1
                else:
                    print(
                        f"    ⚠️ 競合: {worker.name} は introducer_supplier_id="
                        f"{worker.introducer_supplier_id} で既に設定済み（想定: {supplier.id}）"
                    )
                    result["conflict_workers"] += 1
                continue

            if dry_run:
                print(f"    [DRY RUN] 紐付け予定: {worker.name} → {supplier.id}")
            else:
                worker.introducer_supplier_id = supplier.id
                print(f"    → 更新: {worker.name} (introducer_supplier_id = {supplier.id})")
            result["linked_workers"] += 1

    if dry_run:
        print("\n[DRY RUN] コミットはスキップされました")
        return result

    audit_service = AuditService(db)
    audit_service.log(
        "supplier_migration_executed",
        target_type="supplier_migration",
        after_value=result,
        reason="workers.introducer_worker_id → suppliers / workers.introducer_supplier_id 移行",
    )
    db.commit()
    print("\n✅ コミット完了（監査ログも記録）")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="workers → suppliers 紹介者移行")
    parser.add_argument("--dry-run", action="store_true", help="移行プレビュー（デフォルト）")
    parser.add_argument("--commit", action="store_true", help="実際にDBへ反映してコミット")
    args = parser.parse_args()

    if args.dry_run and args.commit:
        raise SystemExit("--dry-run と --commit は同時に指定できません")

    dry_run = not args.commit

    print("=" * 60)
    print("下請け（紹介者）データ移行: workers → suppliers")
    print("=" * 60)
    if dry_run:
        print("\n⚠️ DRY RUN モード: 実際には移行しません（--commit で実移行）\n")
    else:
        print("\n⚠️ 実移行します（DBを書き換えます）\n")

    db = SessionLocal()
    try:
        print("[ステップ1] 紹介者として使われているworkerを特定中...")
        introducers = identify_introducers(db)
        print(f"対象: {len(introducers)} 件")

        if not introducers:
            print("⚠️ 移行対象がありません")
            return

        print("\n[ステップ2] suppliers テーブルへ移行中...")
        result = migrate_to_suppliers(db, introducers, dry_run=dry_run)

        print("\n" + "=" * 60)
        print("移行結果サマリ")
        print("=" * 60)
        print(f"  suppliers作成: {result['created_suppliers']} 件")
        print(f"  workers紐付け: {result['linked_workers']} 件")
        print(f"  既に紐付け済み: {result['already_linked_workers']} 件")
        print(f"  競合（手動確認）: {result['conflict_workers']} 件")
        print(f"  既存supplier使用: {result['used_existing_suppliers']} 件")

        if dry_run:
            print("\n⚠️ DRY RUN モードでした。実際に移行するには --commit を付けて実行してください。")
        else:
            print("\n✅ 移行完了")
            print("\n次のステップ:")
            print("  1. Workers アプリに introducer_supplier_id を追加（手動 or スクリプト）")
            print("  2. suppliers データを Kintone へ同期")
            print("  3. supplier_id ベースの運用フロー確認")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
