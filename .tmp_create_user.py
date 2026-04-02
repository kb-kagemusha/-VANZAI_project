from src.api.jwt_auth import get_password_hash
from src.api.deps import SessionLocal
from src.models.master import User
from src.models.enums import UserRole
from src.models.base import generate_ulid

db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == "admin_web_smoke2").first()
    if existing:
        print("already exists")
    else:
        u = User(
            id=generate_ulid(),
            username="admin_web_smoke2",
            display_name="Sample User 2",
            email="admin_web_smoke2@example.com",
            hashed_password=get_password_hash("SmokeTest123!"),
            role=UserRole.ADMIN.value,
            is_active=True
        )
        db.add(u)
        db.commit()
        print("created: admin_web_smoke2")
finally:
    db.close()
