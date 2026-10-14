"""Client company phone editing; existing contacts stay separate."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.api.schemas import ClientListItem
from src.models.master import Client, User
from src.services.audit import AuditService
from src.services.auth import check_permission, AuthorizationError
from src.models.enums import Permission

router = APIRouter(prefix="/api/clients", tags=["Master"])


class ClientPhoneWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str | None = Field(max_length=20)


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
    return ClientListItem(id=client.id, name=client.name, code=client.code, address=client.address, phone=client.phone, contact_name=client.contact_name, contact_email=client.contact_email, billing_email=client.billing_email)
