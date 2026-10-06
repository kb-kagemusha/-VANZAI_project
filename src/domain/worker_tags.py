"""稼働者タグの定義。自由入力は受け付けず、ここにあるコードだけを保存する。"""

WORKER_TAGS: tuple[tuple[str, str], ...] = (
    ("regular", "常勤"),
    ("spot", "スポット"),
    ("leader", "リーダー可"),
    ("newcomer", "新人"),
)

WORKER_TAG_LABELS: dict[str, str] = dict(WORKER_TAGS)
WORKER_TAG_CODES: tuple[str, ...] = tuple(code for code, _label in WORKER_TAGS)


class UnknownWorkerTagError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def normalize_worker_tags(tags: list[str] | None) -> list[str]:
    """定義済みコードだけを、定義順で重複なく返す。未知のコードは拒否する。"""
    selected: set[str] = set()
    for raw in tags or []:
        code = str(raw).strip()
        if not code:
            continue
        if code not in WORKER_TAG_LABELS:
            raise UnknownWorkerTagError(code)
        selected.add(code)
    return [code for code in WORKER_TAG_CODES if code in selected]


def stored_worker_tags(tags: object) -> list[str]:
    """保存値から、今の定義に含まれるコードだけを定義順で取り出す。"""
    if not isinstance(tags, list):
        return []
    selected = {item for item in tags if isinstance(item, str) and item in WORKER_TAG_LABELS}
    return [code for code in WORKER_TAG_CODES if code in selected]
