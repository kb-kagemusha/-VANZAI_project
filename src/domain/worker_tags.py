"""稼働者タグの定義。自由入力は受け付けず、ここにあるコードだけを保存する。"""

import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

NEWCOMER_CODE = "newcomer"
NEWCOMER_MONTHS = 3

WORKER_TAGS: tuple[tuple[str, str, str], ...] = (
    ("newcomer", "新人", "付けてから3ヶ月で外れます"),
    ("food_d", "飲食D", "飲食店の巡回ができる"),
    ("commercial_d", "商業D", "商業施設の現場ができる"),
    ("shibuya_smoke_d", "渋喫D", "渋谷の喫煙所ができる"),
    ("event_small_d", "小型イベD", "小型イベントなど、4〜5名の現場ができる"),
    ("event_medium_d", "中型イベD", "中型イベントなど、6〜10名の現場ができる"),
    ("event_large_d", "大型イベD", "大型イベントなど、11名以上の現場ができる"),
)

WORKER_TAG_LABELS: dict[str, str] = {code: label for code, label, _description in WORKER_TAGS}
WORKER_TAG_DESCRIPTIONS: dict[str, str] = {code: description for code, _label, description in WORKER_TAGS}
WORKER_TAG_CODES: tuple[str, ...] = tuple(code for code, _label, _description in WORKER_TAGS)
EVENT_SIZE_CODES: tuple[str, ...] = ("event_small_d", "event_medium_d", "event_large_d")
_EVENT_SIZE_CODE_SET = set(EVENT_SIZE_CODES)


class UnknownWorkerTagError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def tokyo_today() -> date:
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _with_single_event_size(selected: set[str], preferred: str | None) -> list[str]:
    """小型・中型・大型イベDは同時に1つだけ残す。後から指定した方を優先する。"""
    if preferred not in _EVENT_SIZE_CODE_SET:
        preferred = None
    kept = {code for code in selected if code not in _EVENT_SIZE_CODE_SET or code == preferred}
    return [code for code in WORKER_TAG_CODES if code in kept]


def normalize_worker_tags(tags: list[str] | None) -> list[str]:
    """定義済みコードだけを、定義順で重複なく返す。未知のコードは拒否する。"""
    selected: set[str] = set()
    preferred_event_size: str | None = None
    for raw in tags or []:
        code = str(raw).strip()
        if not code:
            continue
        if code not in WORKER_TAG_LABELS:
            raise UnknownWorkerTagError(code)
        selected.add(code)
        if code in _EVENT_SIZE_CODE_SET:
            preferred_event_size = code
    return _with_single_event_size(selected, preferred_event_size)


def stored_worker_tags(tags: object) -> list[str]:
    """保存値から、今の定義に含まれるコードだけを定義順で取り出す。"""
    if not isinstance(tags, list):
        return []
    selected: set[str] = set()
    preferred_event_size: str | None = None
    for item in tags:
        if isinstance(item, str) and item in WORKER_TAG_LABELS:
            selected.add(item)
            if item in _EVENT_SIZE_CODE_SET:
                preferred_event_size = item
    return _with_single_event_size(selected, preferred_event_size)


def reconcile_worker_tags(
    stored_tags: object,
    newcomer_until: date | None,
    today: date,
) -> tuple[list[str], date | None, bool]:
    """期限を過ぎた新人タグを外し、期限が無い新人には3ヶ月後を入れる。"""
    visible = stored_worker_tags(stored_tags)
    until = newcomer_until
    if NEWCOMER_CODE in visible:
        if until is None:
            until = add_months(today, NEWCOMER_MONTHS)
        elif today >= until:
            visible = [code for code in visible if code != NEWCOMER_CODE]
            until = None
    else:
        until = None

    stored_list = [item for item in stored_tags if isinstance(item, str)] if isinstance(stored_tags, list) else []
    changed = visible != stored_list or until != newcomer_until
    return visible, until, changed


def newcomer_until_for_assignment(
    previous_tags: object,
    previous_until: date | None,
    next_tags: list[str],
    today: date,
) -> date | None:
    """新人を新たに付けた日を起点に、3ヶ月後の日付を返す。継続中はそのまま。"""
    if NEWCOMER_CODE not in next_tags:
        return None
    previous = stored_worker_tags(previous_tags)
    if NEWCOMER_CODE in previous and previous_until is not None and today < previous_until:
        return previous_until
    return add_months(today, NEWCOMER_MONTHS)


def expire_elapsed_newcomer_tags(db, today: date | None = None) -> None:
    """期限を過ぎた新人タグを保存値から外す。画面を開いたときに反映する。"""
    from sqlalchemy import Text, cast, or_

    from src.models.master import Worker

    current = today or tokyo_today()
    rows = (
        db.query(Worker)
        .filter(Worker.deleted_at.is_(None))
        .filter(
            or_(
                (Worker.newcomer_until.is_not(None)) & (Worker.newcomer_until <= current),
                (Worker.newcomer_until.is_(None)) & cast(Worker.tags, Text).like(f'%"{NEWCOMER_CODE}"%'),
            )
        )
        .all()
    )
    changed = False
    for worker in rows:
        tags, until, did_change = reconcile_worker_tags(worker.tags, worker.newcomer_until, current)
        if did_change:
            worker.tags = tags
            worker.newcomer_until = until
            changed = True
    if changed:
        db.commit()
