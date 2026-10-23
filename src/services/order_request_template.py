"""依頼書の再利用用スナップショット。業務の送付・受諾状態を保存しない。"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import unicodedata

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.master import User, Client, ClientStaff, Site
from src.models.order_request import OrderRequestDocument, OrderRequestTemplate
from src.services.audit import AuditService
from src.services.order_request_format import canonical_conditions, compose_document, parse_sections
from src.services.order_request_service import OrderRequestError, OrderRequestService


def reusable_payload(version, document) -> dict:
    sections = deepcopy(parse_sections(version.request_conditions))
    if sections is None:
        sections = {"content": "\n\n".join(text for text in (version.request_conditions, version.body) if text)}
    sections["work_period"] = {"from": "", "to": "", "excluded_dates": []}
    sections["work_date_detail"] = ""
    schedule = sections.get("schedule")
    if schedule:
        for group in schedule["work_groups"]:
            group.update({"from": "", "to": "", "excluded_dates": []})
        for group in schedule["rate_groups"]:
            group.update({"from": "", "to": ""})
    # 時刻・金額は残し、本文の生成済み日付は日付を空にした構造から組み直す。
    conditions = canonical_conditions(sections)
    sections = parse_sections(conditions)
    return {
        "kind": document.kind,
        "work_date_label": "", "site_id": version.site_id, "site_name": version.site_name,
        "site_address": version.site_address, "request_conditions": canonical_conditions(sections),
        "body": compose_document(sections, work_date_label="", site_name=version.site_name, site_address=version.site_address),
        "contact_name": version.contact_name, "contact_desk": version.contact_desk,
        "counterparty_note": version.counterparty_note,
        "internal_source": {"client_id": version.internal_client_id, "client_staff_id": version.internal_client_staff_id} if version.internal_client_id else None,
        "allow_partial_accept": bool(version.allow_partial_accept),
        "worker_ids": [], "recipient_absences": {}, "phone_first": False, "phone_note": "",
        "tracker_user_id": None, "follow_up_due_on": None, "follow_up_due_time": "21:00",
    }


class OrderRequestTemplateService:
    def __init__(self, session: Session):
        self.session = session

    def get(self, template_id: str) -> OrderRequestTemplate:
        row = self.session.get(OrderRequestTemplate, template_id)
        if row is None or row.archived_at is not None:
            raise OrderRequestError(404, "テンプレートが見つかりません。保存済み一覧を更新してください")
        return row

    def save(self, *, name: str, source_version_id: str, actor: User) -> OrderRequestTemplate:
        version = OrderRequestService(self.session).get_version(source_version_id)
        document = self.session.get(OrderRequestDocument, version.document_id)
        if document.deleted_at is not None:
            raise OrderRequestError(404, "一覧から削除した依頼書はテンプレートに保存できません")
        return self._store(name=name, payload=reusable_payload(version, document), source_version_id=version.id,
                           source_document_number=document.document_number, actor=actor)

    def create(self, *, name: str, content: dict, actor: User) -> OrderRequestTemplate:
        if content["kind"] not in {"formal", "test"}:
            raise OrderRequestError(400, "正式またはテストを選択してください")
        source = content.get("internal_source")
        if source:
            client = self.session.get(Client, source["client_id"])
            if client is None or client.deleted_at is not None:
                raise OrderRequestError(400, "発注元のクライアントを選び直してください")
            staff_id = source.get("client_staff_id")
            staff = self.session.get(ClientStaff, staff_id) if staff_id else None
            if staff_id and (staff is None or staff.deleted_at is not None or not staff.is_active or staff.client_id != client.id):
                raise OrderRequestError(400, "選択した発注元に属する有効な担当者を選んでください")
        if content.get("site_id"):
            site = self.session.get(Site, content["site_id"])
            if site is None or site.deleted_at is not None:
                raise OrderRequestError(400, "稼働場所を選び直してください")
        version = SimpleNamespace(**content, internal_client_id=source["client_id"] if source else None,
                                  internal_client_staff_id=source.get("client_staff_id") if source else None)
        try:
            payload = reusable_payload(version, SimpleNamespace(kind=content["kind"]))
        except ValueError as exc:
            raise OrderRequestError(400, str(exc)) from exc
        return self._store(name=name, payload=payload, source_version_id=None, source_document_number="", actor=actor)

    def _store(self, *, name, payload, source_version_id, source_document_number, actor):
        name = name.strip()
        if not name or len(name) > 100:
            raise OrderRequestError(400, "テンプレート名を1〜100文字で入力してください")
        name_key = unicodedata.normalize("NFKC", name).casefold()
        if len(name_key) > 200:
            raise OrderRequestError(400, "テンプレート名が長すぎます")
        row = OrderRequestTemplate(name=name, name_key=name_key, payload=payload,
                                   source_version_id=source_version_id, source_document_number=source_document_number,
                                   created_by_user_id=actor.id)
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
        except IntegrityError as exc:
            if "name_key" not in str(exc.orig).lower() and "uq_order_request_templates_active_name" not in str(exc.orig).lower():
                raise
            raise OrderRequestError(409, "同じ名前のテンプレートがあります。別の名前を付けてください") from exc
        AuditService(self.session).log("order_request_template_saved", target_type="order_request_template", target_id=row.id,
                                       actor=actor.username, actor_role=actor.role,
                                       after_value={"name": row.name, "source_version_id": source_version_id, "direct_creation": source_version_id is None})
        return row

    def archive(self, template_id: str, *, actor: User) -> OrderRequestTemplate:
        row = self.get(template_id)
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_user_id = actor.id
        AuditService(self.session).log("order_request_template_archived", target_type="order_request_template", target_id=row.id,
                                       actor=actor.username, actor_role=actor.role, before_value={"name": row.name},
                                       after_value={"archived": True})
        self.session.flush()
        return row
