"""権限画面の分類（0.53.8、DEC-125）が、すべての権限を「その他」以外のどれか1つに入れていること。"""
import re
from pathlib import Path

from src.models.enums import Permission

PICKER = Path("apps/admin-web/src/components/RolePermissionPicker.tsx")


def _groups():
    source = PICKER.read_text(encoding="utf-8")
    begin = source.index("= [", source.index("export const PERMISSION_GROUPS"))
    block = source[begin:source.index("\n];", begin)]
    groups = []
    for line in block.splitlines():
        if "key:" not in line:
            continue
        subjects = re.findall(r'"([a-z_]+)"', line.split("subjects:", 1)[1].split("]", 1)[0])
        permissions = re.findall(r'"([a-z_]+)"', line.split("permissions:", 1)[1].split("]", 1)[0]) if "permissions:" in line else []
        groups.append((subjects, permissions))
    return groups


def _subject(value):
    return value if value in ("soft_close", "hard_close") else value.rsplit("_", 1)[0]


def test_every_permission_belongs_to_exactly_one_named_group():
    groups = _groups()
    assert len(groups) == 7
    for permission in Permission:
        hits = [i for i, (subjects, explicit) in enumerate(groups) if permission.value in explicit or _subject(permission.value) in subjects]
        assert hits, f"{permission.value} が権限画面のどの分類にも入っていません"
        # 先に一致した分類に入る（画面と同じ規則）。明示した権限は1つの分類にだけ書く。
        assert sum(permission.value in explicit for _subjects, explicit in groups) <= 1


def test_line_menu_permissions_are_marked():
    source = PICKER.read_text(encoding="utf-8")
    block = source[source.index("export const LINE_MENU_PERMISSIONS"):]
    for value in ("wake_status_read", "order_read", "availability_read", "wake_alert_receive"):
        assert f"{value}:" in block
