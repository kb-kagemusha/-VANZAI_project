"""ダブルヘッダー（2件の依頼書を1件の依頼としてまとめて送り、まとめて返事を受ける）。DEC-148。

- 2件はふつうの依頼書のまま（保存・確定・PDF・請求は既存の処理）。ここは束の作成・2件同時の保存と確定・時間の確認だけ。
- 共通にする欄（区分・送付先・個人の不参加日・追跡担当・期限）は1件目の値を2件目へ写す。
- 段階的な公開：正式区分は FORMAL_BUNDLES_ENABLED が True になるまで作れない（テスト区分で送付〜返事〜起床確認を確かめてから開ける）。
- 運営決定方式（参加可能→運営が確定）と「日付を選んで受諾」は、ダブルヘッダーではまだ使わない（同じ1日の2件のため。運営決定方式は Q8 の対応後に開ける）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.domain import order_bundle as rules
from src.models.order_bundle import (
    OrderRequestBundle,
    OrderRequestBundleDelivery,
    OrderRequestBundleLeg,
    OrderRequestBundleSetting,
)
from src.models.order_request import (
    KIND_FORMAL,
    STATUS_CANCELLED,
    STATUS_DRAFT,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.models.master import User
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.order_request_format import parse_sections
from src.services.order_request_service import OrderRequestError, OrderRequestService

# 正式区分のダブルヘッダーを開けるか。テスト区分で確かめてから True にする（計画 §5、本人指示 2026-11-20）。
FORMAL_BUNDLES_ENABLED = False
FORMAL_CLOSED = "ダブルヘッダーは、いまはテスト区分だけで作れます。テストで送付から返事・起床確認までを確かめてから、正式区分を開けます"
# 2件で共通にする欄（1件目の値を2件目へ写す）
SHARED_FIELDS = ("worker_ids", "recipient_absences", "tracker_user_id", "follow_up_due_on", "follow_up_due_time", "assign_tracker_self")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _label(user: User | None) -> str | None:
    if user is None:
        return None
    return user.display_name or user.username


# ---- 設定（移動に必要な時間の初期値） ------------------------------------------------

def read_settings(session: Session) -> dict:
    row = session.get(OrderRequestBundleSetting, 1)
    if row is None:
        return {"default_travel_minutes": rules.PROVISIONAL_TRAVEL_MINUTES, "provisional": True, "revision": 0,
                "updated_at": None, "updated_by_name": None, "provisional_minutes": rules.PROVISIONAL_TRAVEL_MINUTES}
    user = session.get(User, row.updated_by_user_id)
    return {"default_travel_minutes": row.default_travel_minutes, "provisional": False, "revision": row.revision,
            "updated_at": row.updated_at, "updated_by_name": _label(user), "provisional_minutes": rules.PROVISIONAL_TRAVEL_MINUTES}


def update_settings(session: Session, *, minutes: int, revision: int, actor: User) -> dict:
    _check_minutes(minutes)
    row = session.query(OrderRequestBundleSetting).filter_by(id=1).with_for_update().first()
    current = row.revision if row is not None else 0
    if revision != current:
        raise OrderRequestError(409, "ほかの人が設定を変えました。画面を開き直してください")
    before = row.default_travel_minutes if row is not None else rules.PROVISIONAL_TRAVEL_MINUTES
    if row is None:
        row = OrderRequestBundleSetting(id=1, default_travel_minutes=minutes, revision=1, updated_at=_now(), updated_by_user_id=actor.id)
        session.add(row)
    else:
        row.default_travel_minutes, row.revision = minutes, row.revision + 1
        row.updated_at, row.updated_by_user_id = _now(), actor.id
    AuditService(session).log(
        "order_request_bundle_settings_changed", target_type="order_request_bundle_settings", target_id="1",
        actor=_label(actor), actor_role=actor.role,
        before_value={"default_travel_minutes": before}, after_value={"default_travel_minutes": minutes, "revision": row.revision},
    )
    session.flush()
    return read_settings(session)


def _check_minutes(minutes) -> int:
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0 or minutes > rules.MAX_TRAVEL_MINUTES:
        raise OrderRequestError(400, f"移動に必要な時間は0〜{rules.MAX_TRAVEL_MINUTES}分で入力してください")
    return minutes


# ---- 束の読み取り ------------------------------------------------------------------

def leg_for_document(session: Session, document_id: str | None) -> OrderRequestBundleLeg | None:
    if not document_id:
        return None
    return session.query(OrderRequestBundleLeg).filter_by(document_id=document_id).first()


def legs_for_documents(session: Session, document_ids: set[str]) -> dict[str, OrderRequestBundleLeg]:
    if not document_ids:
        return {}
    rows = session.query(OrderRequestBundleLeg).filter(OrderRequestBundleLeg.document_id.in_(document_ids)).all()
    return {row.document_id: row for row in rows}


def pair_for_delivery(session: Session, delivery_id: str | None) -> OrderRequestBundleDelivery | None:
    if not delivery_id:
        return None
    return (
        session.query(OrderRequestBundleDelivery)
        .filter((OrderRequestBundleDelivery.first_delivery_id == delivery_id) | (OrderRequestBundleDelivery.second_delivery_id == delivery_id))
        .first()
    )


def _legs(session: Session, bundle_id: str) -> list[OrderRequestBundleLeg]:
    return session.query(OrderRequestBundleLeg).filter_by(bundle_id=bundle_id).order_by(OrderRequestBundleLeg.leg_no).all()


def latest_version(session: Session, document_id: str) -> OrderRequestVersion:
    return (
        session.query(OrderRequestVersion)
        .filter_by(document_id=document_id)
        .order_by(OrderRequestVersion.version_no.desc())
        .first()
    )


def _schedule(version: OrderRequestVersion | None) -> dict | None:
    sections = parse_sections(version.request_conditions) if version is not None else None
    return (sections or {}).get("schedule")


def bundle_check(session: Session, bundle: OrderRequestBundle) -> dict:
    versions = [latest_version(session, leg.document_id) for leg in _legs(session, bundle.id)]
    return rules.check(_schedule(versions[0]), _schedule(versions[1]), bundle.travel_minutes)


def partner_summary(session: Session, document_id: str) -> dict | None:
    """相方の依頼書の要点（一覧・詳細・稼働者向け画面の表示用）。"""
    leg = leg_for_document(session, document_id)
    if leg is None:
        return None
    other = session.query(OrderRequestBundleLeg).filter(OrderRequestBundleLeg.bundle_id == leg.bundle_id, OrderRequestBundleLeg.id != leg.id).first()
    if other is None:
        return None
    document = session.get(OrderRequestDocument, other.document_id)
    version = latest_version(session, other.document_id)
    times = rules.leg_times(_schedule(version))
    display = ws.version_display(version)
    return {
        "bundle_id": leg.bundle_id, "leg_no": leg.leg_no, "partner_leg_no": other.leg_no,
        "partner_document_id": document.id, "partner_document_number": document.document_number,
        "partner_version_id": version.id, "partner_status": version.status,
        "partner_project_name": display["project_name"], "partner_site_name": display["site_name"],
        "partner_start": times["start"], "partner_end": times["end"], "partner_end_next_day": times["end_next_day"],
    }


def pdf_note(session: Session, document_id: str | None) -> str | None:
    """PDFの題名の下の1行（DEC-148、本人回答：PDFに1行足す）。番号はLINEと同じく始まりの早い方を1/2にする。"""
    leg = leg_for_document(session, document_id)
    if leg is None:
        return None
    legs = _legs(session, leg.bundle_id)
    versions = [latest_version(session, row.document_id) for row in legs]
    result = rules.check(_schedule(versions[0]), _schedule(versions[1]), 0)
    index = [row.id for row in legs].index(leg.id)
    position = result["order"].index(index) + 1 if result["complete"] else leg.leg_no
    other = legs[1 - index]
    number = session.get(OrderRequestDocument, other.document_id).document_number
    return f"ダブルヘッダー {position}/2（同じ日のもう1件：{number}。受諾・辞退は2件まとめて）"


def bundle_out(session: Session, bundle: OrderRequestBundle) -> dict:
    legs = _legs(session, bundle.id)
    versions = [latest_version(session, leg.document_id) for leg in legs]
    check = rules.check(_schedule(versions[0]), _schedule(versions[1]), bundle.travel_minutes)
    pay = rules.legs_pay_total(_schedule(versions[0]), _schedule(versions[1]))
    out_legs = []
    for leg, version in zip(legs, versions):
        document = session.get(OrderRequestDocument, leg.document_id)
        display = ws.version_display(version)
        times = rules.leg_times(_schedule(version))
        out_legs.append({
            "leg_no": leg.leg_no, "document_id": document.id, "document_number": document.document_number,
            "version_id": version.id, "version_no": version.version_no, "status": version.status,
            "project_name": display["project_name"], "site_name": display["site_name"],
            "start": times["start"], "end": times["end"], "end_next_day": times["end_next_day"],
        })
    pairs = session.query(OrderRequestBundleDelivery).filter_by(bundle_id=bundle.id).all()
    return {
        "id": bundle.id, "kind": bundle.kind, "travel_minutes": bundle.travel_minutes,
        "gap_ack_reason": bundle.gap_ack_reason, "confirmed_at": bundle.confirmed_at,
        "legs": out_legs, "check": check, "send_blockers": rules.send_blockers(check), "pay": pay,
        "pairs": [{"id": p.id, "worker_id": p.worker_id, "first_delivery_id": p.first_delivery_id, "second_delivery_id": p.second_delivery_id} for p in pairs],
        "formal_enabled": FORMAL_BUNDLES_ENABLED,
    }


# ---- 作成・保存 --------------------------------------------------------------------

def _gate_kind(kind: str) -> None:
    if kind == KIND_FORMAL and not FORMAL_BUNDLES_ENABLED:
        raise OrderRequestError(409, FORMAL_CLOSED)


def _leg_payload(payload: dict, shared: dict | None) -> dict:
    """ダブルヘッダーでは使わない設定を外し、共通の欄を1件目にそろえる。"""
    payload = dict(payload)
    if payload.get("based_on_version_id"):
        raise OrderRequestError(409, "ダブルヘッダーは新しい依頼書として作成してください（変更の作成からは作れません）")
    payload.pop("based_on_version_id", None)
    if payload.get("allow_partial_accept") or payload.get("requires_operator_confirmation"):
        raise OrderRequestError(409, "ダブルヘッダーでは「日付を選んで受諾」と「運営が人数調整して参加者を確定する」は使えません")
    payload["allow_partial_accept"] = False
    payload["requires_operator_confirmation"] = False
    if shared is not None:
        for key in SHARED_FIELDS:
            if key in shared:
                payload[key] = shared[key]
    return payload


def _structure_issues(first: OrderRequestVersion, second: OrderRequestVersion, travel_minutes: int) -> dict:
    result = rules.check(_schedule(first), _schedule(second), travel_minutes)
    if result["issues"]:
        raise OrderRequestError(400, result["issues"][0])
    return result


def create(session: Session, *, actor: User, legs: list[dict], travel_minutes: int | None) -> OrderRequestBundle:
    if len(legs) != 2:
        raise OrderRequestError(400, "ダブルヘッダーは1件目と2件目の2件で作成してください")
    kind = legs[0].get("kind") or KIND_FORMAL
    if (legs[1].get("kind") or KIND_FORMAL) != kind:
        raise OrderRequestError(400, "1件目と2件目は同じ区分（正式／テスト）にしてください")
    _gate_kind(kind)
    minutes = _check_minutes(read_settings(session)["default_travel_minutes"] if travel_minutes is None else travel_minutes)
    service = OrderRequestService(session)
    first_payload = _leg_payload(legs[0], None)
    second_payload = _leg_payload(legs[1], first_payload)
    # 日付・日程の形の誤りは、何も作る前に止める（片方だけ残さない）
    pre = rules.check(*[((parse_sections(p.get("request_conditions")) or {}).get("schedule")) for p in (first_payload, second_payload)], minutes)
    if pre["issues"]:
        raise OrderRequestError(400, pre["issues"][0])
    versions = []
    for payload in (first_payload, second_payload):
        payload["internal_source_set"] = "internal_source" in payload
        if payload.pop("assign_tracker_self", False):
            payload["tracker_user_id"] = actor.id
        versions.append(service.create_draft(actor=actor, **payload))
    _structure_issues(versions[0], versions[1], minutes)
    bundle = OrderRequestBundle(kind=kind, travel_minutes=minutes, created_by_user_id=actor.id)
    session.add(bundle)
    session.flush()
    now = _now()
    for no, version in enumerate(versions, start=1):
        session.add(OrderRequestBundleLeg(bundle_id=bundle.id, leg_no=no, document_id=version.document_id,
                                          series_id=ws.ensure_series(session, version), created_at=now))
    session.flush()
    AuditService(session).log(
        "order_request_bundle_created", target_type="order_request_bundle", target_id=bundle.id,
        actor=_label(actor), actor_role=actor.role,
        after_value={"kind": kind, "travel_minutes": minutes, "version_ids": [v.id for v in versions]},
    )
    return bundle


def update(session: Session, *, actor: User, bundle_id: str, legs: list[dict], travel_minutes: int | None, apply_update) -> OrderRequestBundle:
    """下書きの2件を同じ取引で保存する。apply_update(version, fields) は既存の版の保存（routes の変換）を使う。"""
    bundle = get(session, bundle_id)
    current = _legs(session, bundle.id)
    versions = [latest_version(session, leg.document_id) for leg in current]
    if any(v.status != STATUS_DRAFT for v in versions):
        raise OrderRequestError(409, "送付済みのダブルヘッダーは直せません")
    by_id = {v.id: v for v in versions}
    if len(legs) != 2 or {item.get("version_id") for item in legs} != set(by_id):
        raise OrderRequestError(400, "このダブルヘッダーの1件目と2件目を保存してください")
    ordered = sorted(legs, key=lambda item: [v.id for v in versions].index(item["version_id"]))
    first_fields = {k: v for k, v in ordered[0].items() if k != "version_id"}
    second_fields = {k: v for k, v in ordered[1].items() if k != "version_id"}
    for fields in (first_fields, second_fields):
        if fields.get("kind") not in (None, bundle.kind):
            raise OrderRequestError(409, "ダブルヘッダーの区分は作成後に変えられません")
        if fields.get("allow_partial_accept") or fields.get("requires_operator_confirmation"):
            raise OrderRequestError(409, "ダブルヘッダーでは「日付を選んで受諾」と「運営が人数調整して参加者を確定する」は使えません")
    for key in SHARED_FIELDS:
        if key in first_fields:
            second_fields[key] = first_fields[key]
        else:
            second_fields.pop(key, None)
    apply_update(versions[0], first_fields)
    apply_update(versions[1], second_fields)
    # 1件目が触れていない共通の欄も、保存後に2件目へそろえる（ずれを残さない）
    first, second = versions
    second.draft_worker_ids = list(first.draft_worker_ids or [])
    second.draft_recipient_absences = dict(first.draft_recipient_absences or {}) or None
    second.tracker_user_id = first.tracker_user_id
    second.follow_up_due_on, second.follow_up_due_at = first.follow_up_due_on, first.follow_up_due_at
    before = bundle.travel_minutes
    if travel_minutes is not None:
        bundle.travel_minutes = _check_minutes(travel_minutes)
    _structure_issues(first, second, bundle.travel_minutes)
    session.flush()
    if before != bundle.travel_minutes:
        AuditService(session).log(
            "order_request_bundle_travel_changed", target_type="order_request_bundle", target_id=bundle.id,
            actor=_label(actor), actor_role=actor.role,
            before_value={"travel_minutes": before}, after_value={"travel_minutes": bundle.travel_minutes},
        )
    return bundle


def get(session: Session, bundle_id: str) -> OrderRequestBundle:
    bundle = session.get(OrderRequestBundle, bundle_id or "")
    if bundle is None:
        raise OrderRequestError(404, "ダブルヘッダーが見つかりません")
    return bundle


# ---- 確定（2件同時）---------------------------------------------------------------

def confirm(session: Session, *, actor: User, bundle_id: str, gap_reason: str | None) -> OrderRequestBundle:
    bundle = get(session, bundle_id)
    _gate_kind(bundle.kind)
    legs = _legs(session, bundle.id)
    for series_id in sorted(leg.series_id for leg in legs):
        ws.lock_series(session, series_id)
    bundle = get(session, bundle_id)
    versions = [latest_version(session, leg.document_id) for leg in legs]
    if any(v.status != STATUS_DRAFT for v in versions):
        raise OrderRequestError(409, "このダブルヘッダーは確定済みか取消済みです")
    first, second = versions
    if sorted(first.draft_worker_ids or []) != sorted(second.draft_worker_ids or []):
        raise OrderRequestError(409, "1件目と2件目の送付先がそろっていません。保存し直してください")
    result = rules.check(_schedule(first), _schedule(second), bundle.travel_minutes)
    blockers = rules.send_blockers(result)
    if blockers:
        raise OrderRequestError(409, blockers[0])
    reason = " ".join((gap_reason or "").split())[:500]
    if result["short"]:
        if not reason:
            raise OrderRequestError(409, f"移動の間隔が{result['gap_minutes']}分で、移動に必要な時間（{bundle.travel_minutes}分）より短いです。確認した理由を入力してください")
        bundle.gap_ack_reason, bundle.gap_ack_by_user_id, bundle.gap_ack_at = reason, actor.id, _now()
    service = OrderRequestService(session)
    for version in versions:
        service.confirm(version, actor=actor, bundle_ok=True)
    first_rows = {d.worker_id: d for d in session.query(OrderRequestDelivery).filter_by(version_id=first.id).all()}
    second_rows = {d.worker_id: d for d in session.query(OrderRequestDelivery).filter_by(version_id=second.id).all()}
    if set(first_rows) != set(second_rows):
        raise OrderRequestError(409, "1件目と2件目の送付先がそろっていません。保存し直してください")
    now = _now()
    for worker_id, row in first_rows.items():
        session.add(OrderRequestBundleDelivery(bundle_id=bundle.id, worker_id=worker_id, first_delivery_id=row.id,
                                               second_delivery_id=second_rows[worker_id].id, created_at=now))
    bundle.confirmed_at, bundle.confirmed_by_user_id = now, actor.id
    session.flush()
    audit = AuditService(session)
    if result["short"]:
        audit.log("order_request_bundle_gap_acknowledged", target_type="order_request_bundle", target_id=bundle.id,
                  actor=_label(actor), actor_role=actor.role, reason=reason,
                  after_value={"gap_minutes": result["gap_minutes"], "travel_minutes": bundle.travel_minutes})
    audit.log("order_request_bundle_confirmed", target_type="order_request_bundle", target_id=bundle.id,
              actor=_label(actor), actor_role=actor.role,
              after_value={"version_ids": [first.id, second.id], "recipient_count": len(first_rows),
                           "gap_minutes": result["gap_minutes"], "travel_minutes": bundle.travel_minutes})
    return bundle


def pair_versions(session: Session, pair: OrderRequestBundleDelivery) -> list[tuple[OrderRequestDelivery, OrderRequestVersion]]:
    out = []
    for delivery_id in (pair.first_delivery_id, pair.second_delivery_id):
        delivery = session.get(OrderRequestDelivery, delivery_id)
        out.append((delivery, session.get(OrderRequestVersion, delivery.version_id)))
    return out


def ensure_not_bundled(session: Session, document_id: str | None, message: str) -> None:
    if leg_for_document(session, document_id) is not None:
        raise OrderRequestError(409, message)


def is_cancelled(version: OrderRequestVersion | None) -> bool:
    return version is None or version.status == STATUS_CANCELLED
