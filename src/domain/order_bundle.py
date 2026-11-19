"""ダブルヘッダー（同じ日の2件を1件の依頼としてまとめて受ける）の時間の確認。

計画：docs/ops/ORDER_DOUBLE_HEADER_PLAN_2026-11-20.md §4、DEC-148。
- 2件は「1日ごと」の同じ1日だけ（Q6 A）。
- 比べる時刻は、早い方の終了（翌日終了を含む）と、遅い方の開始時間（＝集合時刻。DEC-044。旧データに集合時間があればそれ）。
- 重なり：保存はできるが、確定・送付はできない（Q4 A）。
- 移動時間の不足：送付には確認と理由が必要（Q5 A）。
金額は扱わない（報酬の合計は表示用に legs_pay_total で出すだけ）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# 移動に必要な時間の仮の初期値（分）。運営が画面で変えられる（設定は order_request_bundle_settings）。
PROVISIONAL_TRAVEL_MINUTES = 60
MAX_TRAVEL_MINUTES = 720


def leg_times(schedule: dict | None) -> dict:
    """1件分の日程から、日付・始まり（集合 or 開始）・終わりを取り出す。足りない項目は None。"""
    groups = (schedule or {}).get("work_groups") or []
    result = {"date": None, "start": None, "end": None, "end_next_day": False, "groups": len(groups), "single": True}
    if not groups:
        return result
    if len(groups) != 1 or groups[0].get("date_mode") != "single":
        result["single"] = False
        return result
    group = groups[0]
    result["date"] = group.get("from") or None
    result["start"] = group.get("gathering_time") or group.get("start_time") or None
    result["end"] = group.get("end_time") or None
    result["end_next_day"] = bool(group.get("end_next_day"))
    return result


def _moment(day: str, hm: str, *, next_day: bool = False) -> datetime:
    value = datetime.combine(date.fromisoformat(day), datetime.strptime(hm, "%H:%M").time())
    return value + timedelta(days=1) if next_day else value


def check(first: dict | None, second: dict | None, travel_minutes: int) -> dict:
    """2件の日程（schedule）を比べる。順番は始まりの早い方を1件目にする（order は入力の添字）。

    返り値：
      complete：日付・時刻がそろって判定できたか
      issues：保存前から分かる問題（日付が違う・1日ごとでない）。保存は止める
      overlap：重なり（確定・送付を止める）
      short：移動時間の不足（確認と理由が要る）
      gap_minutes：早い方の終了から遅い方の始まりまで（重なりは負）
    """
    times = [leg_times(first), leg_times(second)]
    issues: list[str] = []
    for no, value in enumerate(times, start=1):
        if not value["single"]:
            issues.append(f"{no}件目の稼働日は「1日ごと」の1日だけにしてください（ダブルヘッダーは同じ1日の2件です）")
    dates = [value["date"] for value in times]
    if all(dates) and dates[0] != dates[1]:
        issues.append("1件目と2件目の稼働日を同じ日にしてください")
    result = {
        "complete": False, "issues": issues, "overlap": False, "short": False, "gap_minutes": None,
        "order": [0, 1], "date": dates[0] or dates[1], "travel_minutes": int(travel_minutes),
        "legs": [{"start": t["start"], "end": t["end"], "end_next_day": t["end_next_day"]} for t in times],
    }
    if issues or not all(dates) or not all(t["start"] and t["end"] for t in times):
        return result
    day = dates[0]
    spans = [(_moment(day, t["start"]), _moment(day, t["end"], next_day=t["end_next_day"])) for t in times]
    order = [0, 1] if spans[0][0] <= spans[1][0] else [1, 0]
    early, late = spans[order[0]], spans[order[1]]
    gap = int((late[0] - early[1]).total_seconds() // 60)
    result.update(complete=True, order=order, gap_minutes=gap, overlap=gap < 0, short=0 <= gap < int(travel_minutes))
    return result


def send_blockers(result: dict) -> list[str]:
    """確定・送付を止める理由（移動時間の不足は含めない。不足は確認と理由で送れる）。"""
    blockers = list(result["issues"])
    if not result["complete"] and not result["issues"]:
        blockers.append("1件目と2件目の稼働日・集合または開始時間・終了時間を入力してください")
    if result["overlap"]:
        blockers.append("1件目と2件目の時間が重なっています。時間を直してください")
    return blockers


def leg_pay(schedule: dict | None) -> dict:
    """1件分の単価（表示用）。日給だけを金額として返す。時給・未入力は None と種類。"""
    rates = (schedule or {}).get("rate_groups") or []
    if len(rates) != 1:
        return {"unit": None, "amount": None}
    rate = rates[0]
    unit = rate.get("unit") or "day"
    try:
        amount = Decimal(str(rate.get("amount"))) if str(rate.get("amount") or "").strip() else None
    except (InvalidOperation, ValueError):
        amount = None
    return {"unit": unit, "amount": amount}


def legs_pay_total(first: dict | None, second: dict | None) -> dict:
    """報酬の合計（Q2 A：2件の単価の和）。どちらも日給で金額があるときだけ合計を出す（今の見込みの決まりと同じ）。"""
    pays = [leg_pay(first), leg_pay(second)]
    hourly = any(p["unit"] == "hour" for p in pays)
    if hourly or any(p["amount"] is None for p in pays):
        return {"total": None, "hourly": hourly, "legs": [str(p["amount"]) if p["amount"] is not None else None for p in pays]}
    total = pays[0]["amount"] + pays[1]["amount"]
    return {"total": format(total, "f"), "hourly": False, "legs": [format(p["amount"], "f") for p in pays]}
