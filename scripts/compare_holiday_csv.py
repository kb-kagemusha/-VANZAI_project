"""Compare a locally supplied Cabinet Office CSV with the shared calendar, read-only."""
import argparse
import csv
from datetime import date
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.services.holiday_calendar import calendar


def official_dates(path: Path, year: int) -> set[str]:
    raw = path.read_bytes()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("cp932")
    days = set()
    for row in csv.reader(content.splitlines()):
        if not row:
            continue
        try:
            parts = [int(part) for part in row[0].strip().replace("-", "/").split("/")]
            day = date(*parts)
        except (ValueError, TypeError):
            continue
        if day.year == year:
            days.add(day.isoformat())
    if not days:
        raise ValueError(f"CSVに{year}年の日付がありません。年とファイルを確認してください")
    return days


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URLが必要です。接続先を確認して環境変数に設定してください")
    official = official_dates(args.csv, args.year)
    engine = create_engine(url)
    with Session(engine) as db:
        current = {row["day"] for row in calendar(db, date(args.year, 1, 1), date(args.year, 12, 31)) if row["is_holiday"]}
    print(f"{args.year}年 公式CSV {len(official)}日、システム {len(current)}日")
    print("CSVのみ: " + (", ".join(sorted(official - current)) or "なし"))
    print("システムのみ: " + (", ".join(sorted(current - official)) or "なし"))
    print("差は自動変更しません。公開範囲と法改正を確認してください。")


if __name__ == "__main__":
    main()
