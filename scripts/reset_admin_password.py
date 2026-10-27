"""Explicit recovery of an existing active administrator; no credentials in output.
New bcrypt hash is supplied through stdin, never argv. Old hash is deferred.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import load_only
from src.models.master import User, VanzaiStaff
from src.services import worker_schedule as ws
from src.services.audit import AuditService


def target(db, username, *, locked=False):
    query = db.query(User).options(load_only(User.id, User.username, User.display_name, User.role,
        User.is_active, User.deleted_at, User.updated_at, User.worker_id, User.vanzai_staff_id)).filter(User.username == username)
    if locked:
        query = query.with_for_update().populate_existing()
    user = query.one_or_none()
    if user is None or user.role != "admin" or not user.is_active or user.deleted_at is not None:
        raise ValueError("The specified account is not an active administrator; unchanged")
    return user


def preview(db, username):
    user = target(db, username)
    staff_name = db.query(VanzaiStaff.name).filter_by(id=user.vanzai_staff_id).scalar() if user.vanzai_staff_id else None
    result = {"user_id": user.id, "username": user.username, "display_name": user.display_name,
              "role": user.role, "staff_name": staff_name,
              "updated_at": user.updated_at.isoformat() if user.updated_at else None}
    result["token"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def reset(db, username, user_id, token, new_hash):
    if not isinstance(new_hash, str) or not re.fullmatch(r"\$2[aby]\$12\$[./A-Za-z0-9]{53}", new_hash):
        raise ValueError("A valid bcrypt cost-12 hash is required through stdin; unchanged")
    user = target(db, username, locked=True)
    info = preview(db, username)
    if user.id != user_id or info["token"] != token:
        raise ValueError("Account changed since preview; unchanged")
    user.hashed_password = new_hash
    user.updated_at = ws.now_utc()
    db.flush()
    AuditService(db).log("admin_password_reset", target_type="user", target_id=user.id,
        actor="user-authorized-maintenance", actor_role="maintenance",
        reason="ユーザーからログインIDを明示された忘失パスワードの再設定",
        after_value={"username": user.username, "password_reset": True, "role_unchanged": True})
    return {"username": user.username, "user_id": user.id, "password_reset": True,
            "role": user.role, "role_and_links_unchanged": True}


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--user-id")
    parser.add_argument("--token")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and not (args.user_id and args.token):
        parser.error("Explicit account ID and preview token are required")
    with SessionLocal() as db:
        if args.apply:
            payload = json.loads(sys.stdin.read(4096))
            result = reset(db, args.username, args.user_id, args.token, payload.get("new_hash"))
            db.commit()
        else:
            result = preview(db, args.username)
        print(json.dumps(result, ensure_ascii=False))
