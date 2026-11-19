"""ダブルヘッダーの実例ファイルの読み込み（試験と scripts/check_double_header_examples.py で共通）。DEC-148。"""
from __future__ import annotations

import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent / "fixtures" / "double_header_examples"
LEG_KEYS = {"project", "site", "gathering", "start", "end", "end_next_day", "unit", "amount", "billing"}


def load_examples() -> list[tuple[Path, dict]]:
    """置かれた実例を読む。`.template.json` は見本なので読まない。形が違えば、どのファイルかを示して止める。"""
    found = []
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        if path.name.endswith(".template.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        legs = data.get("legs")
        if not isinstance(legs, list) or len(legs) != 2 or any(not LEG_KEYS <= set(leg) for leg in legs):
            raise ValueError(f"{path.name}: legs は2件で、各件に {sorted(LEG_KEYS)} が必要です")
        if data.get("expect") is not None and not isinstance(data["expect"], dict):
            raise ValueError(f"{path.name}: expect の形が違います")
        found.append((path, data))
    return found


def schedule_of(leg: dict, day: str) -> dict:
    """実例の1件を、依頼書の日程（1日ごとの1行）の形にする。"""
    work = {"id": "g1", "date_mode": "single", "from": day, "to": day, "start_time": leg["start"], "end_time": leg["end"],
            "end_next_day": bool(leg.get("end_next_day")), "gathering_time": leg.get("gathering") or ""}
    rate = {"id": "r1", "work_group_id": "g1", "date_mode": "single", "from": day, "to": day,
            "amount": str(leg.get("amount") or ""), "unit": leg.get("unit") or "day"}
    return {"version": 1, "work_groups": [work], "rates_follow_work": True, "rate_groups": [rate]}
