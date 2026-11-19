"""Date-grouped request conditions; these are document snapshots, not payroll rates."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class DateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=64)
    date_mode: Literal["single", "range", "weekly"]
    from_: str = Field(alias="from", max_length=10)
    to: str = Field(max_length=10)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    holiday_mode: Literal["include", "exclude"] = "exclude"
    holiday_dates: list[str] = Field(default_factory=list, max_length=3660)
    holiday_review_from: str = ""
    holiday_review_to: str = ""
    # 「毎週」の新しい規則（曜日と祝日のボタン）。旧データは欠落＝legacy（holiday_mode の旧規則のまま）。
    weekly_rule: Literal["legacy", "v2"] = "legacy"
    holiday_selected: bool = False
    # v2：他の行の「祝日」で上書きされるため、この行では稼働しない祝日（サーバーが導出）。
    holiday_skip: list[str] = Field(default_factory=list, max_length=3660)
    # v2：期間を区切る場合だけ true。false の行は全体の稼働期間の全部が対象。
    custom_range: bool = False

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value):
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("曜日の指定を確認してください")
        return sorted(value)

    @field_validator("holiday_dates", "holiday_skip")
    @classmethod
    def valid_holidays(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("祝日が重複しています")
        for day in value:
            if len(day) != 10 or date.fromisoformat(day).isoformat() != day:
                raise ValueError("祝日の日付を確認してください")
        return sorted(value)

    @field_validator("from_", "to")
    @classmethod
    def dates(cls, value):
        if value and (date.fromisoformat(value).isoformat() != value):
            raise ValueError("日付の形式が正しくありません")
        return value

    @model_validator(mode="after")
    def bounds(self):
        if self.date_mode == "single":
            self.to = self.from_
        if self.date_mode != "weekly":
            self.weekly_rule, self.holiday_selected, self.holiday_skip, self.custom_range = "legacy", False, [], False
        if self.from_ and self.to and self.from_ > self.to:
            raise ValueError("終了日は開始日以降にしてください")
        if self.date_mode == "weekly" and self.from_ and self.to:
            if (date.fromisoformat(self.to) - date.fromisoformat(self.from_)).days > 3660:
                raise ValueError("曜日指定の期間は10年以内にしてください")
            if any(day < self.from_ or day > self.to for day in self.holiday_dates):
                raise ValueError("期間外の祝日があります")
        return self


class WorkGroup(DateGroup):
    start_time: str = ""
    end_time: str = ""
    end_next_day: bool = False
    gathering_time: str = ""
    notes: str = Field(default="", max_length=4000)
    # 期間の中の共通の休業日（DEC-065）。旧データは欠落＝空。
    excluded_dates: list[str] = Field(default_factory=list, max_length=366)

    @field_validator("excluded_dates")
    @classmethod
    def excluded_format(cls, value):
        for day in value:
            if not isinstance(day, str) or len(day) != 10 or date.fromisoformat(day).isoformat() != day:
                raise ValueError("休業日の日付の形式が正しくありません")
        if len(set(value)) != len(value):
            raise ValueError("休業日が重複しています")
        return sorted(value)

    @model_validator(mode="after")
    def excluded_range(self):
        if not self.excluded_dates:
            return self
        if self.date_mode == "single":
            raise ValueError("1日ごとの稼働日には休業日を設定できません")
        if not self.from_ or not self.to:
            raise ValueError("休業日を設定する前に、期間の開始日と終了日を入力してください")
        if any(day < self.from_ or day > self.to for day in self.excluded_dates):
            raise ValueError("期間外の休業日があります。期間を変更した場合は休業日も見直してください")
        return self

    @field_validator("start_time", "end_time", "gathering_time")
    @classmethod
    def times(cls, value):
        if value:
            import re
            if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
                raise ValueError("時刻はHH:MMで入力してください")
        return value

    @model_validator(mode="after")
    def time_range(self):
        if self.start_time and self.end_time and not self.end_next_day and self.end_time <= self.start_time:
            raise ValueError("終了時間は開始時間より後にしてください。日をまたぐ場合は翌日を選択してください")
        return self


class RateGroup(DateGroup):
    work_group_id: str | None = Field(default=None, max_length=64)
    amount: str = Field(default="", max_length=18)
    unit: Literal["day", "hour"] = "day"
    lunch_included: bool = True
    transport_included: bool = True
    lunch_note: str = Field(default="", max_length=4000)
    transport_note: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=4000)

    @field_validator("amount")
    @classmethod
    def money(cls, value):
        if not value:
            return value
        import re
        if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,2})?", value):
            raise ValueError("単価は0以上、小数点以下2桁までで入力してください")
        return format(Decimal(value), "f")


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1]
    work_groups: list[WorkGroup] = Field(max_length=120)
    rates_follow_work: bool
    rate_groups: list[RateGroup] = Field(max_length=120)


class WorkPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    from_: str = Field(alias="from", max_length=10)
    to: str = Field(max_length=10)
    # 全体の稼働期間の中の休業日（0.48.5）。None は旧データ（休業日は稼働日の詳細ごとに持つ）。
    excluded_dates: list[str] | None = Field(default=None, max_length=366)

    @field_validator("excluded_dates")
    @classmethod
    def excluded_format(cls, value):
        if value is None:
            return value
        for day in value:
            if not isinstance(day, str) or len(day) != 10 or date.fromisoformat(day).isoformat() != day:
                raise ValueError("休業日の日付の形式が正しくありません")
        if len(set(value)) != len(value):
            raise ValueError("休業日が重複しています")
        return sorted(value)

    @field_validator("from_", "to")
    @classmethod
    def dates(cls, value):
        if value and date.fromisoformat(value).isoformat() != value:
            raise ValueError("稼働日の形式が正しくありません")
        return value


def normalize_work_period(value, schedule=None, *, complete=False):
    try:
        period = WorkPeriod.model_validate(value)
    except (ValidationError, ValueError):
        raise ValueError("稼働日の開始日・終了日を正しい日付で入力してください") from None
    if period.from_ and period.to and period.from_ > period.to:
        raise ValueError("稼働日の終了日は開始日以降にしてください")
    if complete and (not period.from_ or not period.to):
        raise ValueError("全体の稼働日の開始日・終了日を入力してください")
    if period.excluded_dates:
        if not period.from_ or not period.to:
            raise ValueError("休業日を設定する前に、稼働日の開始日と終了日を入力してください")
        if any(day < period.from_ or day > period.to for day in period.excluded_dates):
            raise ValueError("稼働日の期間外の休業日があります。稼働日を変更した場合は休業日も見直してください")
    if schedule:
        for group in schedule["work_groups"]:
            for day in (group["from"], group["to"]):
                if day and ((period.from_ and day < period.from_) or (period.to and day > period.to)):
                    raise ValueError("稼働時間の詳細の日付は、全体の稼働期間内にしてください")
    return period.model_dump(by_alias=True, exclude_none=True)


def apply_period_holidays(schedule: dict, holidays: list[str]) -> dict:
    """全体の休業日を、稼働日の詳細（期間）ごとの休業日に配る。1日ごとの稼働日が休業日に重なるときは拒否する。"""
    days = set(holidays)
    groups = []
    for group in schedule.get("work_groups", []):
        group = dict(group)
        if group.get("date_mode") == "single":
            if group.get("from") in days:
                raise ValueError(f"休業日に「1日ごと」の稼働日があります（{group['from']}）。休業日か稼働時間の詳細を見直してください")
            group["excluded_dates"] = []
        else:
            start, end = group.get("from"), group.get("to")
            group["excluded_dates"] = sorted(d for d in days if start and end and start <= d <= end)
        groups.append(group)
    return {**schedule, "work_groups": groups}


def work_period_label(period):
    return date_label({**period, "date_mode": "range"})


def _ordered(groups):
    if len({g.id for g in groups}) != len(groups):
        raise ValueError("日付・期間の識別子が重複しています")
    result = sorted(groups, key=lambda g: (g.from_ or "9999-12-31", g.to))
    previous = []
    for group in result:
        if not group.from_ or not group.to:
            continue
        for other in previous:
            if group.from_ > other.to or other.from_ > group.to:
                continue
            if group.date_mode != "weekly" and other.date_mode != "weekly":
                raise ValueError("日付・期間が重複しています")
            if group.date_mode == "weekly" and other.date_mode == "weekly" and group.weekly_rule == "v2" and other.weekly_rule == "v2":
                # 新しい規則：同じ曜日、または「祝日」が重なる期間の2行で押されていれば重複（日付の有無に依らず）
                if set(group.weekdays) & set(other.weekdays) or (group.holiday_selected and other.holiday_selected):
                    raise ValueError("日付・期間が重複しています")
                continue
            if set(_days_of(group)) & set(_days_of(other)):
                raise ValueError("日付・期間が重複しています")
        previous.append(group)
    return result


def _weekly_selected(current: date, day: str, *, weekdays, holidays, mode, rule, holiday_selected, skip) -> bool:
    """「毎週」の行がその日を稼働日にするか。旧規則（legacy）は holiday_mode、新規則（v2）は曜日＋「祝日」ボタン。"""
    regular = current.weekday() in weekdays
    if rule == "v2":
        # 曜日の日は、他の行の「祝日」に上書きされた祝日（skip）を除いて稼働。「祝日」を押した行は祝日に稼働。
        return (regular and day not in skip) or (holiday_selected and day in holidays)
    return (regular or day in holidays) if mode == "include" else (regular and day not in holidays)


def _days_of(group) -> list[str]:
    """勤務グループの実勤務日（共通の休業日を除く）。dict と model の両方を受け付ける。"""
    get = group.get if isinstance(group, dict) else lambda key, default=None: getattr(group, "from_" if key == "from" else key, default)
    start, end = get("from"), get("to")
    if not start or not end:
        return []
    excluded = set(get("excluded_dates", None) or [])
    first, last = date.fromisoformat(start).toordinal(), date.fromisoformat(end).toordinal()
    weekly = get("date_mode") == "weekly"
    options = dict(
        weekdays=set(get("weekdays", None) or []), holidays=set(get("holiday_dates", None) or []),
        mode=get("holiday_mode", "exclude"), rule=get("weekly_rule", "legacy") or "legacy",
        holiday_selected=bool(get("holiday_selected", False)), skip=set(get("holiday_skip", None) or []),
    )
    days = []
    for ordinal in range(first, last + 1):
        current = date.fromordinal(ordinal)
        day = current.isoformat()
        if day not in excluded and (not weekly or _weekly_selected(current, day, **options)):
            days.append(day)
    return days


def group_matches_day(group: dict, day: str) -> bool:
    """Check an actual date against a stored group, including its fixed holiday list."""
    start, end = group.get("from"), group.get("to")
    if not start or not end or not start <= day <= end or day in (group.get("excluded_dates") or []):
        return False
    if group.get("date_mode") != "weekly":
        return True
    return _weekly_selected(
        date.fromisoformat(day), day, weekdays=set(group.get("weekdays") or []), holidays=set(group.get("holiday_dates") or []),
        mode=group.get("holiday_mode"), rule=group.get("weekly_rule") or "legacy",
        holiday_selected=bool(group.get("holiday_selected")), skip=set(group.get("holiday_skip") or []),
    )


def expand_work_days(schedule) -> list[dict]:
    """日程を日ごとの実勤務日に展開する（DEC-065）。本文・単価の確認・提示日・稼働予定で共通に使う。"""
    days = []
    for group in schedule.get("work_groups", []) if schedule else []:
        for day in _days_of(group):
            days.append({
                "work_group_id": group["id"],
                "work_date": day,
                "start_time": group.get("start_time", ""),
                "end_time": group.get("end_time", ""),
                "end_next_day": bool(group.get("end_next_day", False)),
            })
    return sorted(days, key=lambda d: (d["work_date"], d["start_time"]))


def work_dates(schedule) -> list[str]:
    """実勤務日の一覧（重複なし・昇順）。"""
    return sorted({d["work_date"] for d in expand_work_days(schedule)})


def normalize_schedule(value, *, complete=False):
    try:
        schedule = Schedule.model_validate(value)
    except ValidationError as exc:
        raise ValueError("日付別の勤務条件を確認してください: " + exc.errors()[0]["msg"].removeprefix("Value error, ")) from None
    _derive_holiday_skip(schedule.work_groups)
    schedule.work_groups = _ordered(schedule.work_groups)
    if schedule.rates_follow_work:
        rates = {g.work_group_id: g for g in schedule.rate_groups}
        if set(rates) != {g.id for g in schedule.work_groups} or len(rates) != len(schedule.rate_groups):
            raise ValueError("単価の設定を稼働日の設定に合わせてください")
        schedule.rate_groups = [rates[g.id].model_copy(update={"date_mode": g.date_mode, "from_": g.from_, "to": g.to, "weekdays": g.weekdays, "holiday_mode": g.holiday_mode, "holiday_dates": g.holiday_dates, "holiday_review_from": g.holiday_review_from, "holiday_review_to": g.holiday_review_to, "weekly_rule": g.weekly_rule, "holiday_selected": g.holiday_selected, "holiday_skip": g.holiday_skip, "custom_range": g.custom_range}) for g in schedule.work_groups]
    elif any(g.work_group_id for g in schedule.rate_groups):
        raise ValueError("個別の単価設定には稼働日の紐付けを指定できません")
    elif any(g.date_mode == "weekly" for g in [*schedule.work_groups, *schedule.rate_groups]):
        raise ValueError("曜日指定は単価を稼働日に合わせてください")
    schedule.rate_groups = _ordered(schedule.rate_groups)
    if complete:
        if not schedule.work_groups or not schedule.rate_groups:
            raise ValueError("勤務条件と単価を入力してください")
        for group in [*schedule.work_groups, *schedule.rate_groups]:
            if not group.from_ or not group.to:
                raise ValueError("すべての日付・期間を入力してください")
        for group in schedule.work_groups:
            if not group.start_time or not group.end_time:
                raise ValueError("すべての開始時間・終了時間を入力してください")
            if group.date_mode == "weekly" and group.weekly_rule == "v2" and not group.weekdays and not group.holiday_selected:
                raise ValueError("「毎週」の行は、曜日か祝日を1つ以上押してください")
            if group.date_mode == "weekly" and (group.holiday_review_from != group.from_ or group.holiday_review_to != group.to):
                raise ValueError("曜日指定の期間について祝日一覧を確認してください")
        for group in schedule.rate_groups:
            if not group.amount:
                raise ValueError("すべての単価を入力してください")
            if not group.lunch_included and not group.lunch_note.strip():
                raise ValueError("昼食代を別途支給する場合は備考を入力してください")
            if not group.transport_included and not group.transport_note.strip():
                raise ValueError("交通費を別途支給する場合は備考を入力してください")
        for work in schedule.work_groups:
            if not _days_of(work):
                raise ValueError("休業日を除くと稼働日がない期間があります")
        # 単価のカバー確認は、休業日を除いた実勤務日について行う（DEC-065）。
        rate_days = set().union(*(_days_of(rate) for rate in schedule.rate_groups))
        for work in schedule.work_groups:
            for day in _days_of(work):
                if day not in rate_days:
                    raise ValueError("単価が設定されていない稼働日があります")
    dumped = schedule.model_dump(by_alias=True)
    for group in [*dumped["work_groups"], *dumped["rate_groups"]]:
        # 旧データ・「毎週」以外の行には新しい項目を持たせない（保存済みの内容を変えない）。
        if group.get("weekly_rule") != "v2":
            for key in ("weekly_rule", "holiday_selected", "holiday_skip", "custom_range"):
                group.pop(key, None)
    return dumped


def _derive_holiday_skip(groups) -> None:
    """v2：「祝日」を押した別の行が同じ祝日を使うとき、曜日の行ではその祝日を稼働にしない（祝日は常に上書き）。"""
    selectors = [g for g in groups if g.date_mode == "weekly" and g.weekly_rule == "v2" and g.holiday_selected and g.from_ and g.to]
    for group in groups:
        if group.date_mode != "weekly" or group.weekly_rule != "v2":
            continue
        skip = []
        if not group.holiday_selected and group.from_ and group.to:
            for day in group.holiday_dates:
                if not group.from_ <= day <= group.to or date.fromisoformat(day).weekday() not in group.weekdays:
                    continue
                if any(other is not group and other.from_ <= day <= other.to and day in other.holiday_dates for other in selectors):
                    skip.append(day)
        group.holiday_skip = sorted(skip)


def date_label(group):
    def jp(value):
        if not value:
            return ""
        d = date.fromisoformat(value)
        return f"{d.year}年{d.month}月{d.day}日"
    start, end = jp(group["from"]), jp(group["to"])
    if group["date_mode"] == "single":
        return start
    if group["date_mode"] == "weekly" and group.get("weekly_rule") == "v2":
        names = "月火水木金土日"
        labels = "・".join(names[i] for i in group.get("weekdays", []))
        if group.get("holiday_selected"):
            labels = f"毎週{labels}・祝日" if labels else "祝日"
        else:
            labels = f"毎週{labels}"
        return f"{start}～{end} {labels}"
    if group["date_mode"] == "weekly":
        names = "月火水木金土日"
        labels = "・".join(names[i] for i in group.get("weekdays", []))
        suffix = "祝日を含む" if group.get("holiday_mode") == "include" else "祝日を除く"
        return f"{start}～{end} 毎週{labels}（{suffix}）"
    if start and end:
        # 休業日は本文の「■休業日」に1回だけ出す（0.48.7。ここに括弧書きで重ねない）
        return f"{start}～{end}"
    return start or (f"～{end}" if end else "")


def schedule_text(schedule):
    hours, fees = [], []
    for group in schedule["work_groups"]:
        lines = [date_label(group)]
        if group["gathering_time"]:
            lines.append(f"集合：{group['gathering_time']}")
        if group["start_time"] or group["end_time"]:
            lines.append(f"稼働：{group['start_time']}～{'翌日 ' if group['end_next_day'] else ''}{group['end_time']}")
        lines.append(group["notes"].strip())
        hours.append("\n".join(filter(None, lines)))
    for group in schedule["rate_groups"]:
        lines = [date_label(group)]
        if group["amount"]:
            amount = format(Decimal(group["amount"]), ",f").rstrip("0").rstrip(".") if "." in group["amount"] else format(Decimal(group["amount"]), ",f")
            lines.append(f"{'時給' if group['unit'] == 'hour' else '日給'}：¥{amount}（税抜）")
        for field, label in (("lunch", "昼食代"), ("transport", "交通費")):
            note = group[f"{field}_note"].strip()
            lines.append(f"{label}：込み" if group[f"{field}_included"] else f"{label}：別途" + (f"（{note}）" if note else ""))
        lines.append(group["notes"].strip())
        fees.append("\n".join(filter(None, lines)))
    return "\n".join(filter(None, (date_label(g) for g in schedule["work_groups"]))), "\n\n".join(hours), "\n\n".join(fees)
