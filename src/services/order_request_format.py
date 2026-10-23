"""案件依頼の本文。欄は既存の本文へ見出し付きでまとめる。"""
import json
import unicodedata
from src.domain.order_schedule import apply_period_holidays, normalize_schedule, normalize_work_period, schedule_text, work_period_label
from src.domain.maps_url import validate_maps_url

FORMAT_ID = "additional-request-v1"
DOCUMENT_TITLE = "【案件依頼】"
# 0.48.10 より前の本文の見出し。PDFの組み立てで、古い本文も見出しを外せるように残す。
LEGACY_DOCUMENT_TITLES = ("【追加案件依頼】",)
DOCUMENT_TITLES = (DOCUMENT_TITLE, *LEGACY_DOCUMENT_TITLES)

# カテゴリ（0.48.10）。「研修」だけはほかの1つと一緒に選べる。本文・PDFには出さない。
TRAINING_CATEGORY = "研修"
CATEGORY_OPTIONS = (
    "飲食店巡回",
    "パーキング/喫煙所系",
    "商業施設/たばこ屋",
    "フェス系",
    "調査系",
    "履行確認",
    TRAINING_CATEGORY,
)
DEFAULT_NOTES = "報酬の期限等その他の事項は、業務委託契約書記載のとおり。"
NO_INCENTIVE = "インセンティブなし"


def incentive_details(sections: dict | None) -> tuple[bool, str]:
    """Legacy text is retained; only explicit, unambiguous negatives mean none."""
    sections = sections or {}
    note = _text(sections.get("incentive"))
    flag = sections.get("incentive_enabled")
    if flag is not None and not isinstance(flag, bool):
        raise ValueError("インセンティブのあり・なしを選択してください")
    if flag is None:
        normalized = "".join(unicodedata.normalize("NFKC", note).split()).lstrip("※・")
        flag = bool(normalized and normalized not in {"なし", "無し", "無", "インセンなし", "インセン無し", "インセンティブなし", "インセンティブ無し"})
    return flag, note if flag else NO_INCENTIVE

_SECTION_KEYS = (
    "project_name",
    "background",
    "meeting_place",
    "site_station",
    "work_date_detail",
    "hours",
    "content",
    "belongings",
    "fee",
    "incentive",
    "notes",
)
_LEGACY_KEYS = (
    "gather_time",
    "work_time",
    "dismiss_time",
    "base_fee",
    "incentive",
)


def parse_sections(request_conditions: str | None) -> dict | None:
    text = (request_conditions or "").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID:
        return None
    sections = {key: _text(data.get(key)) for key in (*_SECTION_KEYS, *_LEGACY_KEYS)}
    if "incentive_enabled" in data:
        if not isinstance(data["incentive_enabled"], bool):
            raise ValueError("インセンティブのあり・なしを選択してください")
        sections["incentive_enabled"] = data["incentive_enabled"]
        if not data["incentive_enabled"]:
            sections["incentive"] = NO_INCENTIVE
    for key in ("previous_hours", "previous_fee", "place_id"):
        if key in data:
            sections[key] = _text(data[key])
    if "categories" in data:
        sections["categories"] = normalize_categories(data["categories"])
    if "maps_url" in data:
        if not isinstance(data["maps_url"], str):
            raise ValueError("Google Mapsの共有URLを入力してください")
        sections["maps_url"] = validate_maps_url(data["maps_url"])
    if sections.get("place_id"):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", sections["place_id"]):
            raise ValueError("Google Mapsの地点を選択し直してください")
    if len(sections["site_station"]) > 100:
        raise ValueError("会場の最寄り駅は100文字以内で入力してください")
    if "site_station_walk_minutes" in data:
        sections["site_station_walk_minutes"] = _walk_minutes(data["site_station_walk_minutes"])
    if "schedule" in data:
        sections["schedule"] = normalize_schedule(data["schedule"])
        _, sections["hours"], sections["fee"] = schedule_text(sections["schedule"])
    if "work_period" in data:
        sections["work_period"] = normalize_work_period(data["work_period"], sections.get("schedule"))
        holidays = sections["work_period"].get("excluded_dates")
        if holidays is not None and sections.get("schedule"):
            # 休業日は全体の稼働日で持ち、稼働日の詳細（期間）ごとに配る（0.48.5）
            sections["schedule"] = normalize_schedule(apply_period_holidays(sections["schedule"], holidays))
            _, sections["hours"], sections["fee"] = schedule_text(sections["schedule"])
    if not sections["hours"]:
        sections["hours"] = _legacy_hours(sections)
    if not sections["fee"]:
        sections["fee"] = _legacy_fee(sections)
    return sections


def normalize_categories(value) -> list[str]:
    """カテゴリを決まった順にそろえる。「研修」以外は1つまで。"""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("カテゴリを選び直してください")
    chosen = {item.strip() for item in value if item.strip()}
    unknown = chosen - set(CATEGORY_OPTIONS)
    if unknown:
        raise ValueError("カテゴリを選び直してください")
    if len(chosen - {TRAINING_CATEGORY}) > 1:
        raise ValueError("カテゴリは「研修」のほかに1つだけ選べます")
    return [item for item in CATEGORY_OPTIONS if item in chosen]


def category_label(sections: dict | None) -> str:
    """一覧に出すカテゴリ（「飲食店巡回、研修」）。なければ空。"""
    if not sections:
        return ""
    return "、".join(sections.get("categories") or [])


def holiday_label(sections: dict) -> str:
    """日程の休業日（期間の中で稼働しない日）を「10月25日（日）、10月28日（水）」の形で。なければ空。"""
    from datetime import date as _date

    period = sections.get("work_period") or {}
    if isinstance(period, dict) and period.get("excluded_dates") is not None:
        days = sorted(period["excluded_dates"])
    else:
        schedule = sections.get("schedule") or {}
        groups = schedule.get("work_groups", []) if isinstance(schedule, dict) else []
        days = sorted({d for g in groups for d in ((g.get("excluded_dates") if isinstance(g, dict) else None) or [])})
    weekdays = "月火水木金土日"
    return "、".join(f"{_date.fromisoformat(d).month}月{_date.fromisoformat(d).day}日（{weekdays[_date.fromisoformat(d).weekday()]}）" for d in days)


def compose_document(sections: dict, *, work_date_label: str, site_name: str, site_address: str | None = None) -> str:
    if "work_period" in sections:
        work_date_label = work_period_label(sections["work_period"])
    notes = _text(sections.get("notes"))
    if notes and not notes.startswith("・"):
        notes = f"・{notes}"
    hours = _text(sections.get("hours")) or _legacy_hours(sections)
    fee = _text(sections.get("fee")) or _legacy_fee(sections)
    incentive = incentive_details(sections)[1]
    return "\n".join(
        [
            DOCUMENT_TITLE,
            "",
            "■案件名",
            _text(sections.get("project_name")),
            "",
            "■背景",
            _text(sections.get("background")),
            "",
            "■稼働場所",
            _text(site_name),
            *([_text(site_address)] if _text(site_address) else []),
            *([sections["maps_url"]] if sections.get("maps_url") else []),
            *(["", "■最寄り駅", station_label(sections)] if station_label(sections) else []),
            *(["", "■集合場所", _text(sections.get("meeting_place"))] if _text(sections.get("meeting_place")) else []),
            "",
            "■稼働日",
            _text(work_date_label),
            *(["", "■休業日", holiday_label(sections)] if holiday_label(sections) else []),
            "",
            "■稼働日の詳細",
            _text(sections.get("work_date_detail")),
            "",
            "■稼働時間",
            hours,
            "",
            "■内容：",
            _text(sections.get("content")),
            "",
            "■持ち物：",
            _text(sections.get("belongings")),
            "",
            "■単価：",
            fee,
            "",
            "■インセンティブ：",
            incentive,
            "",
            "■備考：",
            notes,
        ]
    )


def canonical_conditions(sections: dict) -> str:
    payload = {"format": FORMAT_ID}
    payload.update({key: _text(sections.get(key)) for key in _SECTION_KEYS})
    for key in ("categories", "schedule", "work_period", "previous_hours", "previous_fee", "place_id", "maps_url", "site_station_walk_minutes", "incentive_enabled"):
        if key in sections:
            payload[key] = sections[key]
    return json.dumps(payload, ensure_ascii=False)


def apply_template_fields(request_conditions: str, body: str, *, work_date_label: str, site_name: str, site_address: str | None = None) -> tuple[str, str]:
    """新しい書式なら本文を見出し順に組み直す。古い自由文はそのまま残す。"""
    sections = parse_sections(request_conditions)
    if sections is None:
        return _text(request_conditions), _text(body)
    return (
        canonical_conditions(sections),
        compose_document(sections, work_date_label=work_date_label, site_name=site_name, site_address=site_address),
    )


def _legacy_hours(sections: dict) -> str:
    lines = []
    gather = _text(sections.get("gather_time"))
    work = _text(sections.get("work_time"))
    dismiss = _text(sections.get("dismiss_time"))
    if gather:
        lines.append(f"集合時間：{gather}")
    if work:
        lines.append(f"実施時間：{work}")
    if dismiss:
        lines.append(f"解散時間：{dismiss}")
    return "\n".join(lines)


def _legacy_fee(sections: dict) -> str:
    base = _text(sections.get("base_fee"))
    if not base:
        return ""
    if not base.startswith(("¥", "￥")):
        base = f"¥{base}"
    return f"ベース：{base}"


def _walk_minutes(value) -> int | None:
    """会場の最寄り駅からの徒歩分。空欄は None。0〜120分の整数だけ受け付ける。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("最寄り駅からの徒歩分は0〜120の整数で入力してください")
    try:
        minutes = int(str(value).strip())
    except ValueError:
        raise ValueError("最寄り駅からの徒歩分は0〜120の整数で入力してください") from None
    if str(minutes) != str(value).strip() or not 0 <= minutes <= 120:
        raise ValueError("最寄り駅からの徒歩分は0〜120の整数で入力してください")
    return minutes


def station_label(sections: dict) -> str:
    """「○○駅（徒歩5分）」。駅名がなければ空。"""
    station = _text(sections.get("site_station"))
    if not station:
        return ""
    minutes = sections.get("site_station_walk_minutes")
    return f"{station}（徒歩{minutes}分）" if isinstance(minutes, int) else station


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("~", "～")
