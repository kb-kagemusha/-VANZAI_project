"""本番の PostgreSQL での同時操作の試験（統合計画 ① の公開条件、R-05）。

本番のデータベースで、**この試験が作るテスト区分の依頼書と「【試験】同時操作」の稼働者だけ**を使う。
既存のデータには触れない。物理削除はしない（終了時に依頼書は取消・一覧から外し、稼働者は無効、連携は解除）。

使い方（VPSで .env を読み込んだシェルから。実行前にバックアップを取る）:
  python scripts/test/concurrency_a1.py --rounds 10

確かめること（各ラウンド）:
  S1 全日程の受諾 × 修正版の確定 を同時に → 旧い版の受諾は「確定より前に記録された」場合だけ残る。
     確定の後に旧い版で受諾が記録されていたら不合格（系列のロックが効いていない）。
  S2 日付を選んでの受諾 × 全日程の受諾 を同じ送付行に同時に → 受諾は1回だけ、参加日の状態は1件だけ。
  S3 全日程の受諾 × 取消 を同時に → 取消が先なら受諾は記録されない／受諾が先なら予定は取消で cancelled。
  共通：(系列×稼働者)の再構築をもう一度実行しても変更が出ない（予定が元データと一致）。
結果は標準出力に「合格／不合格」と理由を出し、不合格が1つでもあれば終了コード 1。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import traceback
from datetime import timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.api.deps import SessionLocal  # noqa: E402
from src.models.base import generate_ulid  # noqa: E402
from src.models.line_daily import DeliveryParticipationState, OrderRequestSeries  # noqa: E402
from src.models.line_order import LINK_ACTIVE, LINK_REVOKED, LineWorkerLink  # noqa: E402
from src.models.master import User, Worker  # noqa: E402
from src.models.order_request import ACK_ACKED, OrderRequestDelivery, OrderRequestVersion  # noqa: E402
from src.services import worker_schedule as ws  # noqa: E402
from src.services.line_order import LineOrderService  # noqa: E402
from src.services.order_request_service import OrderRequestError, OrderRequestService  # noqa: E402

PREFIX = "【試験】同時操作"


class NullLine:
    """LINEへは送らない（試験のため）。"""

    def push_messages(self, *_a, **_k):
        raise RuntimeError("送信しない")

    def reply_text(self, *_a, **_k):
        return None

    def reply_messages(self, *_a, **_k):
        return None


def _session():
    return SessionLocal()


def _admin(db) -> User:
    user = db.query(User).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).first()
    if user is None:
        sys.exit("有効な管理者のIDがありません。")
    return user


def _schedule(days: int) -> dict:
    start = ws.today_jst() + timedelta(days=30)
    end = start + timedelta(days=days - 1)
    work = [{"id": "g1", "date_mode": "range", "from": start.isoformat(), "to": end.isoformat(), "start_time": "09:00", "end_time": "18:00", "excluded_dates": []}]
    rates = [{"id": "r1", "work_group_id": "g1", "date_mode": "range", "from": start.isoformat(), "to": end.isoformat(), "amount": "10000", "unit": "day"}]
    return {"version": 1, "work_groups": work, "rates_follow_work": True, "rate_groups": rates}


def _setup_workers(db, count: int, tag: str) -> list[tuple[Worker, str]]:
    result = []
    for i in range(count):
        worker = Worker(id=generate_ulid(), name=f"{PREFIX}{tag}-{i + 1}", is_active=True)
        db.add(worker)
        db.flush()
        line_user = f"U-concurrency-{tag}-{i}-{generate_ulid()[-8:]}"
        db.add(LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id=line_user, status=LINK_ACTIVE, linked_at=ws.now_utc()))
        result.append((worker, line_user))
    db.flush()
    return result


def _confirmed_doc(db, admin: User, worker_ids: list[str], *, partial: bool) -> OrderRequestVersion:
    service = OrderRequestService(db)
    conditions = json.dumps({"format": "additional-request-v1", "project_name": f"{PREFIX}の試験", "schedule": _schedule(3)}, ensure_ascii=False)
    version = service.create_draft(
        actor=admin, kind="test", work_date_label="", site_name="試験会場", site_id=None, site_address=None,
        request_conditions=conditions, body="", contact_name="試験", contact_desk="", counterparty_note=None,
        worker_ids=worker_ids, phone_first=False, phone_contacted_at=None, phone_note=None, tracker_user_id=None,
        follow_up_due_on=ws.today_jst() + timedelta(days=20), allow_partial_accept=partial,
    )
    db.flush()
    return service.confirm(version, actor=admin)


def _run_parallel(funcs) -> list:
    barrier = threading.Barrier(len(funcs))
    results = [None] * len(funcs)

    def runner(i, func):
        db = _session()
        try:
            barrier.wait()
            results[i] = func(db)
            db.commit()
        except Exception as exc:  # 試験の結果として記録する
            db.rollback()
            results[i] = ("error", repr(exc))
        finally:
            db.close()

    threads = [threading.Thread(target=runner, args=(i, f)) for i, f in enumerate(funcs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def _rebuild_is_stable(db, series_id: str, worker_ids: list[str]) -> list[str]:
    problems = []
    for worker_id in worker_ids:
        changes = ws.rebuild(db, series_id, worker_id, actor="concurrency-test")
        if changes:
            problems.append(f"再構築で変更が出た（予定が元データと不一致）: worker={worker_id[-6:]} changes={changes[:3]}")
    db.rollback()
    return problems


def scenario_accept_vs_revise(admin_id: str, tag: str) -> list[str]:
    db = _session()
    admin = db.get(User, admin_id)
    (worker, line_user), = _setup_workers(db, 1, tag)
    worker_id = worker.id
    v1 = _confirmed_doc(db, admin, [worker_id], partial=False)
    delivery_id = db.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == v1.id).one().id
    draft = OrderRequestService(db).revise(v1, actor=admin, reason="同時操作の試験")
    db.commit()
    v1_id, draft_id = v1.id, draft.id
    db.close()

    def accept(s):
        return LineOrderService(s, client=NullLine())._accept(delivery_id, line_user)

    def confirm(s):
        return OrderRequestService(s).confirm(s.get(OrderRequestVersion, draft_id), actor=s.get(User, admin_id)).confirmed_at

    results = _run_parallel([accept, confirm])
    db = _session()
    problems = [f"S1 例外: {r}" for r in results if isinstance(r, tuple) and r[0] == "error"]
    delivery = db.get(OrderRequestDelivery, delivery_id)
    v2 = db.get(OrderRequestVersion, draft_id)
    series = db.get(OrderRequestSeries, v2.series_id)
    if series.answerable_version_id != draft_id:
        problems.append("S1 回答受付版が新しい版になっていない")
    if delivery.ack_status == ACK_ACKED and delivery.acked_at and v2.confirmed_at and delivery.acked_at > v2.confirmed_at:
        problems.append("S1 確定の後に旧い版で受諾が記録された（系列のロックが効いていない）")
    problems += _rebuild_is_stable(db, v2.series_id, [worker_id])
    db.close()
    return problems


def scenario_partial_vs_full(admin_id: str, tag: str) -> list[str]:
    db = _session()
    admin = db.get(User, admin_id)
    (worker, line_user), = _setup_workers(db, 1, tag)
    worker_id = worker.id
    v1 = _confirmed_doc(db, admin, [worker_id], partial=True)
    delivery = db.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == v1.id).one()
    delivery_id, first_day, series_id = delivery.id, delivery.offered_dates[0], v1.series_id
    db.commit()
    db.close()

    def partial(s):
        return LineOrderService(s, client=NullLine()).accept_with_dates(delivery_id, line_user, [first_day])

    def full(s):
        return LineOrderService(s, client=NullLine())._accept(delivery_id, line_user)

    results = _run_parallel([partial, full])
    db = _session()
    problems = [f"S2 例外: {r}" for r in results if isinstance(r, tuple) and r[0] == "error"]
    acked = [r for r in results if isinstance(r, tuple) and r[0] == "acked"]
    if len(acked) != 1:
        problems.append(f"S2 受諾が1回ではない: {results}")
    states = db.query(DeliveryParticipationState).filter(DeliveryParticipationState.delivery_id == delivery_id).count()
    if states != 1:
        problems.append(f"S2 参加日の状態が {states} 件（1件のはず）")
    problems += _rebuild_is_stable(db, series_id, [worker_id])
    db.close()
    return problems


def scenario_accept_vs_cancel(admin_id: str, tag: str) -> list[str]:
    db = _session()
    admin = db.get(User, admin_id)
    (worker, line_user), = _setup_workers(db, 1, tag)
    worker_id = worker.id
    v1 = _confirmed_doc(db, admin, [worker_id], partial=False)
    delivery_id = db.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == v1.id).one().id
    v1_id, series_id = v1.id, v1.series_id
    db.commit()
    db.close()

    def accept(s):
        return LineOrderService(s, client=NullLine())._accept(delivery_id, line_user)

    def cancel(s):
        return OrderRequestService(s).cancel(s.get(OrderRequestVersion, v1_id), actor=s.get(User, admin_id), reason="同時操作の試験").status

    results = _run_parallel([accept, cancel])
    db = _session()
    problems = [f"S3 例外: {r}" for r in results if isinstance(r, tuple) and r[0] == "error"]
    from src.models.line_daily import WorkerScheduleEntry

    active = db.query(WorkerScheduleEntry).filter(
        WorkerScheduleEntry.delivery_id == delivery_id, WorkerScheduleEntry.status.in_(("active", "changing"))
    ).count()
    if active:
        problems.append(f"S3 取消の後に有効な予定が {active} 件残った")
    problems += _rebuild_is_stable(db, series_id, [worker_id])
    db.close()
    return problems


def cleanup(admin_id: str) -> None:
    """この試験が作ったものだけを片付ける（物理削除はしない）。"""
    db = _session()
    admin = db.get(User, admin_id)
    service = OrderRequestService(db)
    workers = db.query(Worker).filter(Worker.name.like(f"{PREFIX}%")).all()
    ids = {w.id for w in workers}
    for link in db.query(LineWorkerLink).filter(LineWorkerLink.worker_id.in_(ids), LineWorkerLink.status == LINK_ACTIVE).all():
        link.status = LINK_REVOKED
        link.revoked_at = ws.now_utc()
        link.revoke_reason = "同時操作の試験の後片付け"
    # JSON の列を含む行は PostgreSQL で DISTINCT できないので、版のIDだけを重複なしで取る
    version_ids = {
        vid
        for (vid,) in db.query(OrderRequestDelivery.version_id).filter(OrderRequestDelivery.worker_id.in_(ids)).distinct().all()
    }
    versions = (
        db.query(OrderRequestVersion).filter(OrderRequestVersion.id.in_(version_ids)).order_by(OrderRequestVersion.created_at).all()
        if version_ids
        else []
    )
    for version in versions:
        if version.status != "cancelled":
            try:
                service.cancel(version, actor=admin, reason="同時操作の試験の後片付け")
            except OrderRequestError:
                pass
    db.flush()
    for version in versions:
        document = service.get_document(version.document_id)
        try:
            service.hide_document(document, actor=admin)
        except OrderRequestError:
            pass
    for worker in workers:
        worker.is_active = False
    db.commit()
    db.close()
    print(f"後片付け：稼働者 {len(workers)} 人を無効、依頼書 {len(versions)} 版を取消・一覧から外した")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--cleanup-only", action="store_true", help="試験はせず、前回の試験が残したものだけを片付ける")
    args = parser.parse_args()
    db = _session()
    if db.get_bind().dialect.name != "postgresql" and os.getenv("CONCURRENCY_SMOKE_SQLITE") != "1":
        sys.exit("PostgreSQL のデータベースで実行してください。")
    admin_id = _admin(db).id
    db.close()
    if args.cleanup_only:
        cleanup(admin_id)
        return
    failures = []
    for round_no in range(1, args.rounds + 1):
        for name, scenario in (("S1", scenario_accept_vs_revise), ("S2", scenario_partial_vs_full), ("S3", scenario_accept_vs_cancel)):
            try:
                problems = scenario(admin_id, f"{name}r{round_no}")
            except Exception:
                problems = [f"{name} 準備で例外:\n{traceback.format_exc()}"]
            status = "合格" if not problems else "不合格"
            print(f"ラウンド{round_no} {name}: {status}")
            for problem in problems:
                print(f"  - {problem}")
            failures += problems
    cleanup(admin_id)
    print("結果：" + ("すべて合格" if not failures else f"不合格 {len(failures)} 件"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
