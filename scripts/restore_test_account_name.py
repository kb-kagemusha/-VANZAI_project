"""誤って改名した本人のテストアカウントを、改名前の監査記録から復元する。"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text, update
from src.models.master import User, Worker
from src.models.transaction import AuditLog
from src.services.audit import AuditService


def restore(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    records = db.query(AuditLog.target_id, AuditLog.before_value, AuditLog.after_value).filter(
        AuditLog.action == "calendar_demo_worker_renamed", AuditLog.target_type == "worker",
        AuditLog.after_value["name"].as_string() == "高橋 直樹",
        AuditLog.before_value["name"].as_string().in_(("テスト アカウント", "テストアカウント")),
    ).order_by(AuditLog.created_at, AuditLog.id).all()
    if len({row.target_id for row in records}) != 1:
        raise RuntimeError("元のアカウントを一意に確認できません。変更は行いません")
    original = records[0]
    worker = db.query(Worker.id, Worker.name, Worker.furigana).filter(Worker.id == original.target_id, Worker.deleted_at.is_(None)).one()
    before = {"name": worker.name, "furigana": worker.furigana}
    restored = {"name": original.before_value["name"], "furigana": original.before_value.get("furigana")}
    if before == restored:
        return {"restored": False, "name": worker.name}
    if before != {"name": original.after_value["name"], "furigana": original.after_value.get("furigana")}:
        raise RuntimeError("改名後に氏名が変更されています。現在の入力を上書きしません")
    actor = db.query(User.username, User.role).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    if actor is None:
        raise RuntimeError("有効な管理者が必要です")
    changed = db.execute(update(Worker).where(Worker.id == worker.id, Worker.name == worker.name, Worker.furigana == worker.furigana).values(**restored))
    if changed.rowcount != 1:
        raise RuntimeError("氏名が同時更新されたため復元を中止しました")
    AuditService(db).log("test_account_name_restored", target_type="worker", target_id=worker.id,
        actor=actor.username, actor_role=actor.role, before_value=before, after_value=restored,
        reason="ユーザー訂正: 本人のテストアカウントをダミー名に変更した誤りを復元")
    db.flush()
    return {"restored": True, "name": restored["name"]}


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    with SessionLocal() as session:
        result = restore(session)
        session.commit()
        print(json.dumps(result, ensure_ascii=False))
