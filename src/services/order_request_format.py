"""追加案件依頼の本文。欄は既存の本文へ見出し付きでまとめる。"""
import json

FORMAT_ID = "additional-request-v1"
DOCUMENT_TITLE = "【追加案件依頼】"
DEFAULT_NOTES = "報酬の期限等その他の事項は、業務委託契約書記載のとおり。"

_SECTION_KEYS = (
    "project_name",
    "background",
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
    if not sections["hours"]:
        sections["hours"] = _legacy_hours(sections)
    if not sections["fee"]:
        sections["fee"] = _legacy_fee(sections)
    return sections


def compose_document(sections: dict, *, work_date_label: str, site_name: str) -> str:
    notes = _text(sections.get("notes"))
    if notes and not notes.startswith("・"):
        notes = f"・{notes}"
    hours = _text(sections.get("hours")) or _legacy_hours(sections)
    fee = _text(sections.get("fee")) or _legacy_fee(sections)
    incentive = _text(sections.get("incentive"))
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
            "",
            "■稼働日",
            _text(work_date_label),
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
    return json.dumps(payload, ensure_ascii=False)


def apply_template_fields(request_conditions: str, body: str, *, work_date_label: str, site_name: str) -> tuple[str, str]:
    """新しい書式なら本文を見出し順に組み直す。古い自由文はそのまま残す。"""
    sections = parse_sections(request_conditions)
    if sections is None:
        return _text(request_conditions), _text(body)
    return (
        canonical_conditions(sections),
        compose_document(sections, work_date_label=work_date_label, site_name=site_name),
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


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("~", "～")
