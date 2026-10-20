"""Client company and contact editing in a single transaction."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.schemas import ClientListItem, ClientStaffItem
from src.models.master import Client, ClientStaff, User
from src.models.base import generate_ulid
from src.services.audit import AuditService
from src.services.auth import check_permission, AuthorizationError
from src.models.enums import Permission

router = APIRouter(prefix="/api/clients", tags=["Master"])


class ClientPhoneWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str | None = Field(max_length=20)


class ClientContactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = Field(None, max_length=26)
    name: str = Field(min_length=1, max_length=100)
    role: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)

    @field_validator("name")
    @classmethod
    def require_name(cls, value):
        if not value.strip():
            raise ValueError("担当者名を入力してください")
        return value.strip()

    @field_validator("role", "phone", "email")
    @classmethod
    def optional_text(cls, value):
        return (value or "").strip() or None


class ClientCompanyResult(ClientListItem):
    contacts: list[ClientStaffItem]


class ClientCompanyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=20)
    postal_code: str | None = Field(None, pattern=r"^[0-9]{7}$")
    address: str | None = None
    notes: str | None = None
    contacts: list[ClientContactWrite] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def require_name(cls, value):
        if value is None or not value.strip():
            raise ValueError("企業名を入力してください")
        return value.strip()

    @field_validator("code", "phone", "address", "notes")
    @classmethod
    def optional_text(cls, value):
        return (value or "").strip() or None


@router.patch("/{client_id}", response_model=ClientCompanyResult)
def update_client_company(client_id: str, body: ClientCompanyWrite, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    try:
        check_permission(user, Permission.MASTER_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(403, str(exc)) from None
    client = db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).with_for_update().first()
    if client is None:
        raise HTTPException(404, "クライアントが見つかりません")
    changes = body.model_dump(exclude_unset=True, exclude={"contacts"})
    if changes.get("code") and db.query(Client.id).filter(Client.id != client_id, func.lower(Client.code) == changes["code"].lower()).first():
        raise HTTPException(409, "同じコードのクライアントが既に存在します")
    # Validate every supplied ID before changing company or contact rows.
    contacts = db.query(ClientStaff).filter(ClientStaff.client_id == client_id, ClientStaff.deleted_at.is_(None)).order_by(ClientStaff.id).with_for_update().all()
    by_id = {contact.id: contact for contact in contacts}
    ids = [contact.id for contact in body.contacts if contact.id is not None]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "担当者が重複しています")
    if any(contact_id not in by_id for contact_id in ids):
        raise HTTPException(404, "この企業の担当者が見つかりません。再読み込みしてください")
    primary = [contact for contact in contacts if contact.name == client.contact_name]
    primary_id = primary[0].id if len(primary) == 1 else None
    before = {key: getattr(client, key) for key in changes}
    changed = {key: value for key, value in changes.items() if before[key] != value}
    for key, value in changed.items():
        setattr(client, key, value)
    for item in body.contacts:
        values = item.model_dump(exclude_unset=True, exclude={"id"})
        if item.id is not None:
            contact = by_id[item.id]
            old = {key: getattr(contact, key) for key in values}
            updates = {key: value for key, value in values.items() if old[key] != value}
            for key, value in updates.items():
                setattr(contact, key, value)
            if updates:
                AuditService(db).log("client_staff_updated", target_type="client_staff", target_id=contact.id, actor=user.username, actor_role=user.role,
                                     before_value={key: old[key] for key in updates}, after_value=updates)
        else:
            contact = ClientStaff(id=generate_ulid(), client_id=client_id, is_active=True, **values)
            db.add(contact)
            contacts.append(contact)
            AuditService(db).log("client_staff_created", target_type="client_staff", target_id=contact.id, actor=user.username, actor_role=user.role,
                                 after_value={"client_id": client_id, **values})
        if contact.id == primary_id or (not client.contact_name and len(contacts) == 1):
            for key, value in {"contact_name": contact.name, "contact_email": contact.email}.items():
                if getattr(client, key) != value:
                    before[key] = getattr(client, key)
                    changed[key] = value
                    setattr(client, key, value)
    if changed:
        AuditService(db).log("client_updated", target_type="client", target_id=client.id, actor=user.username, actor_role=user.role,
                             before_value={key: before[key] for key in changed}, after_value=changed)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "同じコードのクライアントが既に存在します") from None
    return ClientCompanyResult(id=client.id, name=client.name, code=client.code, address=client.address, phone=client.phone, contact_name=client.contact_name, contact_email=client.contact_email, billing_email=client.billing_email, postal_code=client.postal_code, notes=client.notes,
                               contacts=[ClientStaffItem(id=contact.id, client_id=client_id, name=contact.name, role=contact.role, phone=contact.phone, email=contact.email, is_active=contact.is_active, notes=contact.notes) for contact in contacts])


@router.patch("/{client_id}/phone", response_model=ClientListItem)
def update_client_phone(client_id: str, body: ClientPhoneWrite, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    try:
        check_permission(user, Permission.MASTER_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(403, str(exc)) from None
    client = db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).with_for_update().first()
    if client is None:
        raise HTTPException(404, "クライアントが見つかりません")
    client.phone = (body.phone or "").strip() or None
    AuditService(db).log("client_updated", target_type="client", target_id=client.id, actor=user.username, actor_role=user.role, after_value={"changed_fields": ["phone"]})
    db.commit()
    return ClientListItem(id=client.id, name=client.name, code=client.code, address=client.address, phone=client.phone, contact_name=client.contact_name, contact_email=client.contact_email, billing_email=client.billing_email, postal_code=client.postal_code, notes=client.notes)
