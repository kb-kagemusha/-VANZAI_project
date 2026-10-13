"""Date-grouped request conditions; these are document snapshots, not payroll rates."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class DateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=64)
    date_mode: Literal["single", "range"]
    from_: str = Field(alias="from", max_length=10)
    to: str = Field(max_length=10)

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
        if self.from_ and self.to and self.from_ > self.to:
            raise ValueError("終了日は開始日以降にしてください")
        return self


class WorkGroup(DateGroup):
    start_time: str = ""
    end_time: str = ""
    end_next_day: bool = False
    gathering_time: str = ""
    notes: str = Field(default="", max_length=4000)

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


def _ordered(groups):
    if len({g.id for g in groups}) != len(groups):
        raise ValueError("日付・期間の識別子が重複しています")
    result = sorted(groups, key=lambda g: (g.from_ or "9999-12-31", g.to))
    previous_end = ""
    for group in result:
        if not group.from_ or not group.to:
            continue
        if previous_end and group.from_ <= previous_end:
            raise ValueError("日付・期間が重複しています")
        previous_end = group.to
    return result


def normalize_schedule(value, *, complete=False):
    try:
        schedule = Schedule.model_validate(value)
    except ValidationError as exc:
        raise ValueError("日付別の勤務条件を確認してください: " + exc.errors()[0]["msg"].removeprefix("Value error, ")) from None
    schedule.work_groups = _ordered(schedule.work_groups)
    schedule.rate_groups = _ordered(schedule.rate_groups)
    if schedule.rates_follow_work:
        rates = {g.work_group_id: g for g in schedule.rate_groups}
        if set(rates) != {g.id for g in schedule.work_groups} or len(rates) != len(schedule.rate_groups):
            raise ValueError("単価の設定を稼働日の設定に合わせてください")
        schedule.rate_groups = [rates[g.id].model_copy(update={"date_mode": g.date_mode, "from_": g.from_, "to": g.to}) for g in schedule.work_groups]
    elif any(g.work_group_id for g in schedule.rate_groups):
        raise ValueError("個別の単価設定には稼働日の紐付けを指定できません")
    if complete:
        if not schedule.work_groups or not schedule.rate_groups:
            raise ValueError("勤務条件と単価を入力してください")
        for group in [*schedule.work_groups, *schedule.rate_groups]:
            if not group.from_ or not group.to:
                raise ValueError("すべての日付・期間を入力してください")
        for group in schedule.work_groups:
            if not group.start_time or not group.end_time:
                raise ValueError("すべての開始時間・終了時間を入力してください")
        for group in schedule.rate_groups:
            if not group.amount:
                raise ValueError("すべての単価を入力してください")
            if not group.lunch_included and not group.lunch_note.strip():
                raise ValueError("昼食代を別途支給する場合は備考を入力してください")
            if not group.transport_included and not group.transport_note.strip():
                raise ValueError("交通費を別途支給する場合は備考を入力してください")
        for work in schedule.work_groups:
            cursor = date.fromisoformat(work.from_).toordinal()
            last = date.fromisoformat(work.to).toordinal()
            for rate in schedule.rate_groups:
                start, end = date.fromisoformat(rate.from_).toordinal(), date.fromisoformat(rate.to).toordinal()
                if start <= cursor <= end:
                    cursor = end + 1
                if cursor > last:
                    break
            if cursor <= last:
                raise ValueError("単価が設定されていない稼働日があります")
    return schedule.model_dump(by_alias=True)


def date_label(group):
    def jp(value):
        if not value:
            return ""
        d = date.fromisoformat(value)
        return f"{d.year}年{d.month}月{d.day}日"
    start, end = jp(group["from"]), jp(group["to"])
    if group["date_mode"] == "single":
        return start
    if start and end:
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
