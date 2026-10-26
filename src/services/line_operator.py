"""Read-only LINE operator portal. Existing User permissions remain authoritative."""
from datetime import date, timedelta, timezone
import hashlib
import secrets
from sqlalchemy.orm import Session
from src.domain.line_operator_config import operator_entry
from src.domain.line_registration_entry import registration_login_channel_id
from src.models.base import generate_ulid
from src.models.enums import Permission
from src.models.line_operator import LineOperatorSession
from src.models.master import User, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.services import line_id_token, worker_schedule as ws
from src.services.auth import has_permission, is_management_role
from src.services.audit import AuditService


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

    def wake(self, user, day: date):
        require(user, Permission.WAKE_STATUS_READ)
        from src.services.wake_status import build_wake_status
        value = build_wake_status(self.db, day)
        # Explicit allowlist: no phone/contact notes/addresses or suggested manual escalation.
        keys = ("worker_id", "worker_name", "first_start", "wake_reported_at", "overlap_warning")
        return {"date": value["date"], "total": value["total"], "reported": value["reported"], "items": [
            {**{key: row[key] for key in keys}, "entries": [{key: entry[key] for key in ("project_name", "site_name", "start_time", "end_time", "end_next_day", "status")} for entry in row["entries"]]}
            for row in sorted(value["items"], key=lambda r: (bool(r["wake_reported_at"]), r["first_start"] or "99:99", r["worker_name"]))]}

    def calendar(self, user, start: date, end: date, kind: str):
        if start > end or (end - start).days > 61:
            raise OperatorError(400, "表示期間は62日以内で指定してください。")
        if kind == "orders":
            require(user, Permission.ORDER_READ)
            from src.services.participation_calendar import build
            rows = build(self.db, start=start.isoformat(), end=end.isoformat())
            # Keep only the calendar data needed on a phone, never return the source document.
            return {"kind": kind, "days": [{"date": day["date"], "events": [{
                "project_name": event["project_name"], "site_name": event["site_name"],
                **{bucket: [{"worker_id": p["worker_id"], "name": p["name"]} for p in event[bucket]] for bucket in ("ok", "changing", "unanswered", "unavailable")}
            } for event in day["events"]]} for day in rows]}
        require(user, Permission.AVAILABILITY_READ)
        from src.services.operator_calendar import availability
        return availability(self.db, start, end)
