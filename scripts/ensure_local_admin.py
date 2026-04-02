"""Create or update a local admin user for browser smoke checks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.deps import SessionLocal
from src.api.jwt_auth import get_password_hash
from src.models.master import User
from src.models.enums import UserRole


USERNAME = "admin_web_smoke"
EMAIL = "admin_web_smoke@example.com"
PASSWORD = "SmokeTest123!"


def main() -> None:
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == USERNAME).first()
        if user is None:
            user = session.query(User).filter(User.email == EMAIL).first()
        if user is None:
            user = User(
                username=USERNAME,
                email=EMAIL,
                hashed_password=get_password_hash(PASSWORD),
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            session.add(user)
        else:
            user.username = USERNAME
            user.email = EMAIL
            user.hashed_password = get_password_hash(PASSWORD)
            user.role = UserRole.ADMIN.value
            user.is_active = True

        session.commit()
        print(f"created_or_updated={USERNAME}")
        print(f"password={PASSWORD}")
    finally:
        session.close()


if __name__ == "__main__":
    main()