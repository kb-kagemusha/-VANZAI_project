"""Invitation, immutable operator application and admin approval. DEC-110."""
import hashlib
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text, or_
from src.models.base import generate_ulid
from src.models.master import RegistrationRequest, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.models.operator_registration import OperatorRegistrationDetail
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestError
from src.domain.line_operator_config import operator_entry
from src.services.line_messaging import build_line_client


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize(name, phone):
    name = name.strip()
    phone = re.sub(r"[\s()（）－ー-]", "", unicodedata.normalize("NFKC", phone))
    if not name or len(name) > 100 or not re.fullmatch(r"0[0-9]{9,10}", phone):
        raise OrderRequestError(422, "氏名と電話番号（0から始まる10〜11桁）を確認してください")
    return name, phone


class OperatorRegistrationService:
    def __init__(self, db):
        self.db = db
        self.audit = AuditService(db)

    def log(self, action, row, actor):
        self.audit.log(action, target_type="registration_request", target_id=row.id,
                       actor=actor, after_value={"status": row.status, "request_type": "operator_staff"})

    def issue(self, actor):
        entry = operator_entry()
        if not entry["enabled"]:
            raise OrderRequestError(409, "運営用LINE登録の設定が未完了です。運営用LIFFを設定してください")
        token = secrets.token_urlsafe(32)
        row = RegistrationRequest(id=generate_ulid(), request_type="operator_staff", status="link_issued",
                                  source_type="line_operator", public_token_hash=digest(token), expires_at=now() + timedelta(hours=24), failed_attempts=0)
        self.db.add(row)
        self.db.flush()
        self.db.add(OperatorRegistrationDetail(request_id=row.id, is_open=False))
        self.log("operator_registration_invited", row, actor.id)
        return {"request_id": row.id, "expires_at": row.expires_at,
                "url": f"https://liff.line.me/{entry['liff_id']}?invite={token}"}

    def request(self, request_id, *, lock=False):
        query = select(RegistrationRequest).where(RegistrationRequest.id == request_id,
            RegistrationRequest.request_type == "operator_staff", RegistrationRequest.source_type == "line_operator", RegistrationRequest.deleted_at.is_(None))
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self.db.execute(query).scalar_one_or_none()
        if row is None:
            raise OrderRequestError(404, "運営スタッフの申請が見つかりません")
        return row, self.db.get(OperatorRegistrationDetail, row.id)

    def invitation(self, token):
        row = self.db.execute(select(RegistrationRequest).where(RegistrationRequest.public_token_hash == digest(token),
            RegistrationRequest.request_type == "operator_staff", RegistrationRequest.source_type == "line_operator",
            RegistrationRequest.deleted_at.is_(None)).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if not row:
            raise OrderRequestError(404, "招待リンクを確認できません。管理者へ再発行を依頼してください")
        detail = self.db.get(OperatorRegistrationDetail, row.id)
        if detail.revoked_at or row.locked_at:
            raise OrderRequestError(410, "この招待は失効しています。管理者へ連絡してください")
        if row.status == "link_issued" and (not row.expires_at or row.expires_at.replace(tzinfo=timezone.utc) <= now()):
            raise OrderRequestError(410, "招待の期限が切れました。管理者へ再発行を依頼してください")
        return row, detail

    def submit(self, token, subject, name, phone, client):
        name, phone = normalize(name, phone)
        row, detail = self.invitation(token)
        if row.status != "link_issued":
            if detail.line_user_id == subject and detail.name == name and detail.phone == phone:
                return {"request_id": row.id, "status": row.status}
            raise OrderRequestError(409, "この招待は申請済みです。申請内容は変更できません")
        self.identity_lock(subject)
        if self.db.query(LineStaffLink).filter_by(line_user_id=subject, status="active").first():
            raise OrderRequestError(409, "このLINEは既に運営スタッフへ連携済みです。管理者へ連絡してください")
        if self.db.query(OperatorRegistrationDetail).filter_by(line_user_id=subject, is_open=True).first():
            raise OrderRequestError(409, "運営スタッフの申請を確認中です。管理者の承認をお待ちください")
        profile_name = client.profile_name(subject)
        if not profile_name:
            raise OrderRequestError(409, "公式LINEとの連携を確認できません。友だち追加・ブロック解除後に再試行してください。改善しない場合は管理者へ連絡してください")
        detail.name, detail.phone, detail.line_user_id, detail.line_display_name = name, phone, subject, profile_name
        detail.is_open = True
        row.status, row.submitted_at = "pending", now()
        self.log("operator_registration_submitted", row, "line-operator")
        self.db.flush()
        return {"request_id": row.id, "status": row.status}

    def identity_lock(self, subject):
        if self.db.bind.dialect.name == "postgresql":
            # Same namespace as legacy OPS-code linking.
            key = int.from_bytes(hashlib.sha256(subject.encode()).digest()[:8], "big", signed=True)
            self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def view(self, request_id):
        row, detail = self.request(request_id)
        candidates = self.db.query(VanzaiStaff).filter(VanzaiStaff.deleted_at.is_(None), VanzaiStaff.is_active.is_(True),
            or_(VanzaiStaff.name == detail.name, VanzaiStaff.phone == detail.phone)).order_by(VanzaiStaff.name, VanzaiStaff.id).limit(30).all() if detail.name else []
        return {"request_id": row.id, "status": row.status, "name": detail.name, "phone": detail.phone,
                "line_display_name": detail.line_display_name, "staff_id": row.approved_target_id,
                "candidates": [{"id": staff.id, "name": staff.name, "phone": staff.phone, "profile_revision": staff.profile_revision} for staff in candidates]}

    def approve(self, request_id, actor, staff_id=None, revision=None):
        row, detail = self.request(request_id, lock=True)
        if row.status != "pending" or not detail.is_open or detail.revoked_at:
            raise OrderRequestError(409, "この申請は承認できません。最新の状態を確認してください")
        if not build_line_client().profile_name(detail.line_user_id):
            raise OrderRequestError(409, "公式LINEとの連携を確認できません。本人の友だち追加・ブロック状態を確認してください")
        staff = None
        if staff_id:
            staff = self.db.execute(select(VanzaiStaff).where(VanzaiStaff.id == staff_id).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
            if not staff or staff.deleted_at or not staff.is_active or revision != staff.profile_revision:
                raise OrderRequestError(409, "反映先の情報が変更されています。内容を読み込み直してください")
        elif self.db.query(VanzaiStaff).filter(VanzaiStaff.deleted_at.is_(None), or_(VanzaiStaff.name == detail.name, VanzaiStaff.phone == detail.phone)).first():
            raise OrderRequestError(409, "同じ氏名または電話番号の運営スタッフがいます。既存の登録を確認して紐付け先を選んでください")
        self.identity_lock(detail.line_user_id)
        if self.db.query(LineStaffLink).filter(LineStaffLink.status == "active", or_(LineStaffLink.line_user_id == detail.line_user_id, LineStaffLink.staff_id == staff_id)).first():
            raise OrderRequestError(409, "LINEの紐付けが変更されています。管理者が現在の連携を確認してください")
        if staff is None:
            staff = VanzaiStaff(id=generate_ulid(), name=detail.name, phone=detail.phone, management_roles=[], is_active=True, profile_revision=1)
            self.db.add(staff)
            self.db.flush()
            self.audit.log("operator_staff_created", target_type="vanzai_staff", target_id=staff.id, actor=actor.id, actor_role=actor.role, after_value={"source": "line_registration", "profile_revision": 1})
        self.db.add(LineStaffLink(id=generate_ulid(), staff_id=staff.id, line_user_id=detail.line_user_id, line_display_name=detail.line_display_name, status="active", linked_at=now()))
        row.status, row.reviewed_at, row.reviewed_by = "approved", now(), actor.id
        row.approved_target_type, row.approved_target_id = "vanzai_staff", staff.id
        detail.is_open = False
        self.log("operator_registration_approved", row, actor.id)
        self.audit.log("operator_line_linked", target_type="vanzai_staff", target_id=staff.id, actor=actor.id, actor_role=actor.role, after_value={"line_linked": True})
        self.db.flush()
        return {"request_id": row.id, "status": row.status, "staff_id": staff.id}

    def reject(self, request_id, actor, reason):
        if not reason.strip():
            raise OrderRequestError(422, "却下理由を入力してください")
        row, detail = self.request(request_id, lock=True)
        if row.status != "pending":
            raise OrderRequestError(409, "確認待ちではありません")
        row.status, row.reviewed_at, row.reviewed_by = "rejected", now(), actor.id
        detail.is_open = False
        self.audit.log("operator_registration_rejected", target_type="registration_request", target_id=row.id, actor=actor.id, actor_role=actor.role, reason=reason.strip())
        return {"request_id": row.id, "status": row.status}

    def revoke(self, request_id, actor):
        row, detail = self.request(request_id, lock=True)
        if row.status != "link_issued":
            raise OrderRequestError(409, "未申請の招待だけ失効できます。申請済みの場合は確認待ちから審査してください")
        detail.revoked_at = now()
        row.locked_at = now()
        self.log("operator_registration_invite_revoked", row, actor.id)
        return {"request_id": row.id, "status": "revoked"}
