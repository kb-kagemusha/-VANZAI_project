"""既存ダミー3名にディレクター可能の表示例を付ける（他のタグは保持）。"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text, update
from src.models.master import Worker, User
from src.services.audit import AuditService
from src.domain.worker_tags import normalize_worker_tags

DEMO_DIRECTORS = ("山田 太郎", "渡邊 健太郎", "長谷川 亜香里")


def apply(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(2026102301)"))
    actor = db.query(User.username, User.role).filter(User.role == "admin", User.is_active.is_(True), User.deleted_at.is_(None)).order_by(User.id).first()
    rows = db.query(Worker.id, Worker.name, Worker.tags).filter(Worker.name.in_(DEMO_DIRECTORS), Worker.is_active.is_(True), Worker.deleted_at.is_(None)).all()
    if actor is None or len(rows) != 3 or len({w.name for w in rows}) != 3:
        raise RuntimeError("指定したダミー3名を一意に確認できないため変更しません")
    changed = 0
    for worker in rows:
        tags = normalize_worker_tags([*(worker.tags or []), "director"])
        if tags == worker.tags:
            continue
        db.execute(update(Worker).where(Worker.id == worker.id).values(tags=tags))
        AuditService(db).log("calendar_demo_director_tagged", target_type="worker", target_id=worker.id,
            actor=actor.username, actor_role=actor.role, before_value={"tags":worker.tags}, after_value={"tags":tags},
            reason="ユーザー指定: 名簿・登録一覧でディレクターの表示例を確認")
        changed += 1
    db.flush()
    return {"tagged": changed, "directors": [w.name for w in rows]}


if __name__ == "__main__":
    from src.api.deps import SessionLocal
    with SessionLocal() as session:
        result = apply(session)
        session.commit()
        print(json.dumps(result, ensure_ascii=False))
