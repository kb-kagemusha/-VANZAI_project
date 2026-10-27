"""Read-only LINE operator portal. Existing User permissions remain authoritative."""
from datetime import date, timedelta, timezone
import hashlib
import secrets
from sqlalchemy.orm import Session
from src.domain.line_operator_config import operator_entry
from src.domain.line_registration_entry import registration_login_channel_id
from src.models.base import generate_ulid
from src.models.enums import Permission
from src.models.line_daily import WAKE_CONTACT_CLAIM
from src.models.line_operator import LineOperatorFileToken, LineOperatorSession
from src.models.master import User, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.services import line_id_token, worker_schedule as ws
from src.services.auth import has_permission, is_management_role
from src.services.audit import AuditService


def _handler(contacts: list[dict]):
    """今の対応者：最後の「引き受けた」記録のあとに、起床確認・欠勤の結果がまだ無い人。"""
    from src.models.line_daily import WAKE_CONTACT_RESOLVED
    handler = None
    for contact in contacts:
        if contact["result"] == WAKE_CONTACT_CLAIM:
            handler = {"actor_name": contact["actor_name"], "actor_user_id": contact.get("actor_user_id"), "at": contact["created_at"]}
        elif contact["result"] in WAKE_CONTACT_RESOLVED:
            handler = None
    return handler


def _public_handler(handler, user):
    if not handler:
        return None
    return {"actor_name": handler["actor_name"], "at": handler["at"], "is_me": handler["actor_user_id"] == user.id}


class OperatorError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def identity(db: Session, subject: str):
    link = db.query(LineStaffLink).filter_by(line_user_id=subject, status="active").one_or_none()
    staff = db.get(VanzaiStaff, link.staff_id) if link else None
    if not staff or not staff.is_active or staff.deleted_at is not None:
        raise OperatorError(403, "有効な運営スタッフのLINE連携がありません。管理者へお問い合わせください。")
    users = db.query(User).filter(User.vanzai_staff_id == staff.id, User.is_active.is_(True), User.deleted_at.is_(None)).all()
    if len(users) != 1 or not is_management_role(users[0].role, db):
        raise OperatorError(403, "運営スタッフと有効な管理画面IDの対応を、管理者に確認してください。")
    return link, staff, users[0]


def require(user: User, permission: Permission):
    if not has_permission(user, permission):
        raise OperatorError(403, "この情報を見る権限がありません。管理者へお問い合わせください。")


class LineOperatorService:
    def __init__(self, db: Session):
        self.db = db

    def issue(self, id_token: str):
        if not operator_entry()["enabled"]:
            raise OperatorError(503, "運営用のLINE画面は準備中です。")
        try:
            subject = line_id_token.verify_id_token(id_token, registration_login_channel_id())
        except line_id_token.LineIdTokenError:
            raise OperatorError(401, "LINEの本人確認に失敗しました。LINEから開き直してください。") from None
        link, staff, user = identity(self.db, subject)
        token = secrets.token_urlsafe(32)
        now = ws.now_utc()
        self.db.add(LineOperatorSession(id=generate_ulid(), token_hash=hashlib.sha256(token.encode()).hexdigest(), link_id=link.id, staff_id=staff.id, user_id=user.id, created_at=now, expires_at=now + timedelta(minutes=30)))
        AuditService(self.db).log("operator_session_issued", target_type="vanzai_staff", target_id=staff.id, actor=user.id)
        return {"token": token, "expires_at": (now + timedelta(minutes=30)).isoformat()}

    def authenticate(self, token: str):
        if not token or len(token) > 200:
            raise OperatorError(401, "LINEから開き直してください。")
        row = self.db.query(LineOperatorSession).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).one_or_none()
        expires = row.expires_at.replace(tzinfo=timezone.utc) if row and not row.expires_at.tzinfo else row.expires_at if row else None
        if not row or expires <= ws.now_utc():
            raise OperatorError(401, "本人確認の期限が切れました。LINEから開き直してください。")
        original = self.db.get(LineStaffLink, row.link_id)
        if not original or original.status != "active":
            raise OperatorError(403, "LINE連携が解除されています。管理者へお問い合わせください。")
        link, staff, user = identity(self.db, original.line_user_id)
        if (link.id, staff.id, user.id) != (row.link_id, row.staff_id, row.user_id):
            raise OperatorError(401, "登録の対応が変わりました。LINEから開き直してください。")
        return staff, user

    def me(self, staff, user):
        return {"name": staff.name, "phone": staff.phone, "permissions": {
            "wake": has_permission(user, Permission.WAKE_STATUS_READ),
            "availability": has_permission(user, Permission.AVAILABILITY_READ),
            "orders": has_permission(user, Permission.ORDER_READ)}}

    def wake(self, user, day: date, include_test: bool = False):
        require(user, Permission.WAKE_STATUS_READ)
        from src.services.wake_status import build_wake_status
        value = build_wake_status(self.db, day, include_test=include_test)
        # Explicit allowlist: no phone/contact notes/addresses here. The phone is returned only by claim().
        keys = ("worker_id", "worker_name", "first_start", "wake_reported_at", "overlap_warning")
        from src.models.line_daily import WakeMonitorSend
        from src.services.wake_monitor import deadline_for
        sends = {}
        for send in self.db.query(WakeMonitorSend).filter(WakeMonitorSend.work_date == day, WakeMonitorSend.status == "sent").all():
            sends.setdefault((send.worker_id, bool(send.is_test)), set()).add(send.kind)
        items = []
        for row in value["items"]:
            times = deadline_for(day, row["first_start"])
            contacts = [c for c in row["contacts"] if c["result"] != WAKE_CONTACT_CLAIM]
            items.append({
                **{key: row[key] for key in keys},
                "next_action": {key: row["next_action"][key] for key in ("step", "label", "priority")},
                "handler": _public_handler(_handler(row["contacts"]), user),
                "last_result": ({"label": contacts[-1]["result_label"], "actor_name": contacts[-1]["actor_name"], "at": contacts[-1]["created_at"]} if contacts else None),
                "entries": [{key: entry[key] for key in ("project_name", "site_name", "start_time", "end_time", "end_next_day", "status", "is_test")} for entry in row["entries"]],
                "is_test": all(entry["is_test"] for entry in row["entries"]),
                # 起床の監視（0.54.0、DEC-126）：期限、本人への催促・運営への知らせを送ったか
                "deadline": times[0].strftime("%H:%M") if times else None,
                "reminded": "worker_reminder" in sends.get((row["worker_id"], all(e["is_test"] for e in row["entries"])), set()),
                "alerted": "operator_alert" in sends.get((row["worker_id"], all(e["is_test"] for e in row["entries"])), set()),
            })
        # Same order as the admin screen: whoever needs action now comes first.
        items.sort(key=lambda r: (r["next_action"]["priority"], r["first_start"] or "99:99", r["worker_name"]))
        return {"date": value["date"], "is_today": day == ws.today_jst(), "include_test": include_test, "total": value["total"], "reported": value["reported"], "items": items}

    def _wake_row(self, day: date, worker_id: str):
        from src.services.wake_status import build_wake_status
        if day != ws.today_jst():
            raise OperatorError(409, "連絡の記録は当日の分だけできます。")
        # テストの予定の人も、動作確認のため連絡・記録できる
        row = next((r for r in build_wake_status(self.db, day, include_test=False)["items"] if r["worker_id"] == worker_id), None)
        if row is None:
            row = next((r for r in build_wake_status(self.db, day, include_test=True)["items"] if r["worker_id"] == worker_id), None)
        if row is None:
            raise OperatorError(404, "この日の予定がある稼働者ではありません。画面を更新してください。")
        return row

    def claim(self, staff, user, day: date, worker_id: str, takeover: bool):
        """「私が連絡します」。引き受けた人にだけ電話番号を返し、ほかの運営には対応中と表示する（0.53.8、DEC-125）。"""
        require(user, Permission.WAKE_STATUS_READ)
        from src.models.line_daily import WakeContactLog
        from src.models.master import Worker
        row = self._wake_row(day, worker_id)
        if row["wake_reported_at"] is not None:
            raise OperatorError(409, "この方は起床の報告済みです。")
        handler = _handler(row["contacts"])
        if handler and handler["actor_user_id"] != user.id and not takeover:
            raise OperatorError(409, f"{handler['actor_name']}さんが対応中です。")
        created = not handler or handler["actor_user_id"] != user.id
        if created:
            log = WakeContactLog(worker_id=worker_id, contact_date=day, result=WAKE_CONTACT_CLAIM, note=None,
                                 is_test=all(e["is_test"] for e in row["entries"]),
                                 actor_user_id=user.id, actor_name=staff.name[:100], created_at=ws.now_utc())
            self.db.add(log)
            self.db.flush()
            AuditService(self.db).log("wake_contact_claimed", target_type="wake_contact_log", target_id=log.id, actor=user.id, actor_role=user.role,
                                      after_value={"worker_id": worker_id, "date": day.isoformat(), "takeover_from": handler["actor_name"] if handler else None})
        worker = self.db.get(Worker, worker_id)
        return {"worker_id": worker_id, "worker_name": row["worker_name"], "phone": (worker.phone or None) if worker else None, "handler_name": staff.name, "new_claim": created}

    def record(self, staff, user, day: date, worker_id: str, result: str, note: str):
        """電話などの結果を記録する。管理画面の起床状況と同じ記録（追記のみ）。"""
        require(user, Permission.WAKE_STATUS_READ)
        from src.models.line_daily import WAKE_CONTACT_RESULTS, WakeContactLog
        if result not in WAKE_CONTACT_RESULTS or result == WAKE_CONTACT_CLAIM:
            raise OperatorError(400, "連絡の結果を選び直してください。")
        row = self._wake_row(day, worker_id)
        log = WakeContactLog(worker_id=worker_id, contact_date=day, result=result, note=note.strip() or None,
                             is_test=all(e["is_test"] for e in row["entries"]),
                             actor_user_id=user.id, actor_name=staff.name[:100], created_at=ws.now_utc())
        self.db.add(log)
        self.db.flush()
        AuditService(self.db).log("wake_contact_recorded", target_type="wake_contact_log", target_id=log.id, actor=user.id, actor_role=user.role,
                                  after_value={"worker_id": worker_id, "date": day.isoformat(), "result": result, "note": log.note, "via": "line_operator"})
        return {"id": log.id, "result": result, "result_label": WAKE_CONTACT_RESULTS[result]}

    def calendar(self, user, start: date, end: date, kind: str, include_test: bool = False):
        if start > end or (end - start).days > 61:
            raise OperatorError(400, "表示期間は62日以内で指定してください。")
        if kind == "orders":
            require(user, Permission.ORDER_READ)
            from src.services.participation_calendar import build
            rows = build(self.db, start=start.isoformat(), end=end.isoformat(), include_test=include_test)
            # Keep only the calendar data needed on a phone, never return the source document.
            return {"kind": kind, "days": [{"date": day["date"], "events": [{
                "project_name": event["project_name"], "site_name": event["site_name"],
                "version_id": event["version_id"], "document_number": event["document_number"], "is_test": event["is_test"],
                **{bucket: [{"worker_id": p["worker_id"], "name": p["name"]} for p in event[bucket]] for bucket in ("ok", "changing", "unanswered", "unavailable")}
            } for event in day["events"]]} for day in rows]}
        require(user, Permission.AVAILABILITY_READ)
        from src.services.operator_calendar import availability
        return availability(self.db, start, end)

    # ---- 発注依頼書（受領状況と依頼書本体。0.53.8、DEC-125） ----------------------------------
    def orders(self, user, start: date, end: date, include_test: bool = False):
        """回答受付中の正式な依頼書のうち、日程が期間に入るもの。送付先ごとの受領状況を返す（金額・内部メモは返さない）。"""
        require(user, Permission.ORDER_READ)
        if start > end or (end - start).days > 61:
            raise OperatorError(400, "表示期間は62日以内で指定してください。")
        from src.models.line_daily import OrderRequestSeries
        from src.models.order_request import (ACK_ACKED, ACK_DECLINE_PENDING, ACK_DECLINED, KIND_FORMAL, SEND_ACCEPTED, SEND_UNKNOWN,
                                              OrderRequestDelivery, OrderRequestDocument, OrderRequestVersion)
        from src.models.master import Worker
        today = ws.today_jst()
        names = {w.id: w.name for w in self.db.query(Worker).all()}
        items = []
        for series in self.db.query(OrderRequestSeries).filter(OrderRequestSeries.answerable_version_id.is_not(None)).all():
            version = self.db.get(OrderRequestVersion, series.answerable_version_id)
            document = self.db.get(OrderRequestDocument, version.document_id) if version else None
            if version is None or document is None or document.deleted_at is not None or (document.kind != KIND_FORMAL and not include_test):
                continue
            dates = sorted({d["work_date"] for d in ws.version_work_days(version)})
            in_range = [d for d in dates if start.isoformat() <= d <= end.isoformat()]
            # 日程が自由文の依頼書は、今日を含む表示のときだけ出す（日付で絞れないため）
            if not in_range and not (not dates and start <= today <= end):
                continue
            groups = {"acked": [], "unacked": [], "decline_pending": [], "declined": [], "unsent": []}
            for delivery in self.db.query(OrderRequestDelivery).filter(OrderRequestDelivery.version_id == version.id).all():
                if delivery.view_revoked:
                    continue
                name = names.get(delivery.worker_id, delivery.worker_name_snapshot)
                if delivery.ack_status == ACK_DECLINED:
                    key = "declined"
                elif delivery.ack_status == ACK_DECLINE_PENDING:
                    key = "decline_pending"
                elif delivery.ack_status == ACK_ACKED:
                    key = "acked"
                elif delivery.send_status in (SEND_ACCEPTED, SEND_UNKNOWN):
                    key = "unacked"
                else:
                    key = "unsent"
                groups[key].append({"worker_id": delivery.worker_id, "name": name, "acked_at": delivery.acked_at.isoformat() if delivery.acked_at else None})
            for rows in groups.values():
                rows.sort(key=lambda r: r["name"])
            display = ws.version_display(version)
            items.append({
                "version_id": version.id, "document_number": document.document_number, "version_no": version.version_no,
                "project_name": display["project_name"], "site_name": display.get("site_name") or "",
                "work_date_label": version.work_date_label, "first_date": dates[0] if dates else None, "last_date": dates[-1] if dates else None,
                "next_date": next((d for d in dates if d >= today.isoformat()), None),
                "has_pdf": bool(version.pdf_object_key), "dispatch_stopped": version.dispatch_stopped, "is_test": document.kind != KIND_FORMAL, **groups,
            })
        items.sort(key=lambda r: (r["next_date"] is None, r["next_date"] or r["last_date"] or "", r["document_number"]))
        return {"start": start.isoformat(), "end": end.isoformat(), "items": items}

    def pdf_link(self, staff, user, version_id: str):
        require(user, Permission.ORDER_READ)
        from src.models.order_request import OrderRequestDocument, OrderRequestVersion
        from src.services.line_messaging import line_settings
        version = self.db.get(OrderRequestVersion, version_id or "")
        document = self.db.get(OrderRequestDocument, version.document_id) if version else None
        if version is None or document is None or document.deleted_at is not None or not version.pdf_object_key:
            raise OperatorError(404, "この依頼書は開けません。")
        base = line_settings().public_api_base
        if not base.startswith("https://"):
            raise OperatorError(503, "いまは依頼書を開けません。管理者へお問い合わせください。")
        token = secrets.token_urlsafe(32)
        now = ws.now_utc()
        row = LineOperatorFileToken(id=generate_ulid(), token_hash=hashlib.sha256(token.encode()).hexdigest(), version_id=version.id,
                                    staff_id=staff.id, user_id=user.id, created_at=now, expires_at=now + timedelta(minutes=FILE_MINUTES))
        self.db.add(row)
        AuditService(self.db).log("operator_order_pdf_link", target_type="order_request_version", target_id=version.id, actor=user.id, actor_role=user.role)
        return {"url": f"{base.rstrip('/')}/api/line/operator/order-files/{token}", "expires_minutes": FILE_MINUTES}

    def read_file(self, token: str):
        """短命リンクのPDFを返す。開く時点でも、本人の連携・役割・権限・依頼書の状態を確かめ直す。"""
        from src.models.order_request import OrderRequestDocument, OrderRequestVersion
        from src.services.order_request_pdf import order_request_pdf_filename, project_name_from_document
        from src.services.order_request_service import OrderRequestError, OrderRequestService
        if not token or len(token) > 80 or "/" in token:
            raise OperatorError(404, "リンクが無効です。LINEから開き直してください。")
        row = self.db.query(LineOperatorFileToken).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).one_or_none()
        expires = (row.expires_at.replace(tzinfo=timezone.utc) if not row.expires_at.tzinfo else row.expires_at) if row else None
        if row is None or expires <= ws.now_utc():
            raise OperatorError(404, "リンクの期限が切れました。LINEから開き直してください。")
        staff = self.db.get(VanzaiStaff, row.staff_id)
        user = self.db.get(User, row.user_id)
        link = self.db.query(LineStaffLink).filter_by(staff_id=row.staff_id, status="active").one_or_none()
        if not staff or not user or not link:
            raise OperatorError(403, "LINE連携が解除されています。")
        _link, current_staff, current_user = identity(self.db, link.line_user_id)
        if (current_staff.id, current_user.id) != (row.staff_id, row.user_id):
            raise OperatorError(403, "登録の対応が変わりました。LINEから開き直してください。")
        require(current_user, Permission.ORDER_READ)
        version = self.db.get(OrderRequestVersion, row.version_id)
        document = self.db.get(OrderRequestDocument, version.document_id) if version else None
        if version is None or document is None or document.deleted_at is not None:
            raise OperatorError(404, "この依頼書は開けません。")
        try:
            content = OrderRequestService(self.db).read_pdf(version)
        except OrderRequestError as exc:
            raise OperatorError(exc.status_code, exc.detail) from None
        filename = order_request_pdf_filename(work_date_label=version.work_date_label,
                                              project_name=project_name_from_document(version.request_conditions, version.body))
        AuditService(self.db).log("operator_order_pdf_read", target_type="order_request_version", target_id=version.id, actor=current_user.id, actor_role=current_user.role)
        return content, filename


FILE_MINUTES = 10
