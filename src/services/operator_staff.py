"""Profile and signed-webhook LINE linking for existing VANZAI staff."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from src.models.base import generate_ulid
from src.models.master import VanzaiStaff
from src.models.operator_staff import LineStaffLink, LineStaffLinkCode
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestError

CODE_PREFIX = "OPS-"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def now():
    return datetime.now(timezone.utc)


def code_hash(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class OperatorStaffService:
    def __init__(self, session):
        self.session = session
        self.audit = AuditService(session)

    def staff(self, staff_id, *, lock=False):
        query = select(VanzaiStaff).where(VanzaiStaff.id == staff_id, VanzaiStaff.deleted_at.is_(None))
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        staff = self.session.execute(query).scalar_one_or_none()
        if staff is None:
            raise OrderRequestError(404, "運営スタッフが見つかりません")
        return staff

    def active_link(self, staff_id):
        return self.session.query(LineStaffLink).filter_by(staff_id=staff_id, status="active").one_or_none()

    def issue_code(self, staff_id, actor):
        staff = self.staff(staff_id, lock=True)
        if not staff.is_active:
            raise OrderRequestError(409, "無効な運営スタッフには紐付けできません")
        if self.active_link(staff_id):
            raise OrderRequestError(409, "すでに紐付け済みです。変更する場合は先に解除してください")
        moment = now()
        self.session.query(LineStaffLinkCode).filter(LineStaffLinkCode.staff_id == staff_id, LineStaffLinkCode.used_at.is_(None), LineStaffLinkCode.expires_at > moment).update({"expires_at": moment})
        code = CODE_PREFIX + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        expiry = moment + timedelta(minutes=30)
        self.session.add(LineStaffLinkCode(id=generate_ulid(), staff_id=staff_id, code_hash=code_hash(code), expires_at=expiry, created_by_user_id=actor.id, created_at=moment))
        self.audit.log("operator_line_code_issued", target_type="vanzai_staff", target_id=staff_id, actor=actor.id, actor_role=actor.role, after_value={"expires_in_minutes": 30})
        self.session.flush()
        return code, expiry

    def consume_code(self, code_text, line_user_id, client):
        rejected = ("staff_rejected", "この運営スタッフ用コードは使えません。管理画面で新しいコードを発行してください。")
        if not line_user_id or len(line_user_id) > 64:
            return rejected
        code = self.session.execute(select(LineStaffLinkCode).where(LineStaffLinkCode.code_hash == code_hash(code_text))).scalar_one_or_none()
        if code is None:
            return rejected
        try:
            staff = self.staff(code.staff_id, lock=True)
        except OrderRequestError:
            return rejected
        code = self.session.execute(select(LineStaffLinkCode).where(LineStaffLinkCode.id == code.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
        # PostgreSQL row locks serialize staff changes; identity lock serializes two different staff codes for one LINE user.
        if self.session.bind.dialect.name == "postgresql":
            lock_key = int.from_bytes(hashlib.sha256(line_user_id.encode()).digest()[:8], "big", signed=True)
            self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        self.session.refresh(code)
        expiry = code.expires_at.replace(tzinfo=timezone.utc) if code.expires_at.tzinfo is None else code.expires_at
        if code.used_at or expiry <= now() or not staff.is_active:
            return rejected
        if self.active_link(staff.id) or self.session.query(LineStaffLink).filter_by(line_user_id=line_user_id, status="active").first():
            return "staff_conflict", "別の運営スタッフとの紐付けが残っています。管理担当者に解除を依頼してください。"
        link = LineStaffLink(id=generate_ulid(), staff_id=staff.id, line_user_id=line_user_id, line_display_name=client.profile_name(line_user_id), status="active", linked_at=now())
        self.session.add(link)
        code.used_at = now()
        self.audit.log("operator_line_linked", target_type="vanzai_staff", target_id=staff.id, actor="line-webhook", after_value={"line_linked": True})
        self.session.flush()
        return "staff_linked", "運営スタッフとして公式LINEに紐付けました。運営に関する連絡を受け取れます。"

    def revoke(self, staff_id, actor, reason):
        self.staff(staff_id, lock=True)
        link = self.active_link(staff_id)
        if not link:
            raise OrderRequestError(404, "LINE紐付けが見つかりません")
        link.status, link.revoked_at, link.revoked_by_user_id, link.revoke_reason = "revoked", now(), actor.id, reason
        self.audit.log("operator_line_revoked", target_type="vanzai_staff", target_id=staff_id, actor=actor.id, actor_role=actor.role, reason=reason, after_value={"line_linked": False})

    def unfollow(self, line_user_id):
        links = self.session.query(LineStaffLink).filter_by(line_user_id=line_user_id, status="active").with_for_update().all()
        for link in links:
            link.status, link.revoked_at, link.revoke_reason = "revoked", now(), "公式LINEの友だち解除"
            self.audit.log("operator_line_revoked", target_type="vanzai_staff", target_id=link.staff_id, actor="line-webhook", reason=link.revoke_reason, after_value={"line_linked": False})
