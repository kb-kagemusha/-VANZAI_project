"""Import the public Cabinet Office holiday CSV into the shared calendar."""
import argparse
from datetime import date

from src.api.deps import SessionLocal
from src.models.master import User
from src.services.holiday_calendar import calendar, import_official_csv
from src.services.order_request_service import OrderRequestError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        actor = db.query(User).filter(User.username == args.username, User.is_active.is_(True), User.deleted_at.is_(None)).one_or_none()
        if actor is None:
            parser.error("有効なユーザーが見つかりません。ユーザー名を確認してください")
        try:
            status = import_official_csv(db, actor=actor, reason="デプロイ時の初回取り込み")
        except OrderRequestError as exc:
            db.rollback()
            raise SystemExit(exc.detail) from exc
        db.commit()
        print(status["label"])
        if status["notice"]:
            print(status["notice"])
        for day in (date(2026, 11, 3), date(2026, 11, 23)):
            row = next(iter(calendar(db, day, day)), None)
            print(day.isoformat(), "なし" if row is None else f"{row['name']} revision={row['revision']} source={row['source']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
