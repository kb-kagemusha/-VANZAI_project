"""Create or update a local worker user for staff-mobile smoke checks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.deps import SessionLocal
from src.api.jwt_auth import get_password_hash
from src.models.enums import UserRole
from src.models.master import User, Worker


USERNAME = "staff_mobile_smoke"
EMAIL = "staff_mobile_smoke@example.com"
PASSWORD = "SmokeTest123!"
WORKER_NOTE = "browser-smoke-mobile-worker"
WORKER_NAME = "モバイル確認スタッフ"
WORKER_EMAIL = "smoke-mobile-worker@example.com"


def main() -> None:
    session = SessionLocal()
    try:
        worker = session.query(Worker).filter(Worker.notes == WORKER_NOTE).first()
        if worker is None:
            worker = Worker(
                name=WORKER_NAME,
                email=WORKER_EMAIL,
                notes=WORKER_NOTE,
                is_active=True,
            )
            session.add(worker)
            session.flush()
        else:
            worker.name = WORKER_NAME
            worker.email = WORKER_EMAIL
            worker.is_active = True

        user = session.query(User).filter(User.username == USERNAME).first()
        if user is None:
            user = session.query(User).filter(User.email == EMAIL).first()
        if user is None:
            user = User(
                username=USERNAME,
                email=EMAIL,
                hashed_password=get_password_hash(PASSWORD),
                role=UserRole.WORKER.value,
                is_active=True,
                worker_id=worker.id,
            )
            session.add(user)
        else:
            user.username = USERNAME
            user.email = EMAIL
            user.hashed_password = get_password_hash(PASSWORD)
            user.role = UserRole.WORKER.value
            user.is_active = True
            user.worker_id = worker.id

        session.commit()
        print(f"created_or_updated={USERNAME}")
        print(f"worker_id={worker.id}")
        print(f"password={PASSWORD}")
    finally:
        session.close()


if __name__ == "__main__":
    main()