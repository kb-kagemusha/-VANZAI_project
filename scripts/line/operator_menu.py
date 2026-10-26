"""Publish individual operator menus without changing the default worker menu.

Runtime settings are supplied by the deployment wrapper. No secret files are read here.
"""
import argparse
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.domain.line_registration_config import load_line_registration_config
from src.domain.line_operator_config import load_line_operator_config, operator_entry
load_line_registration_config()
load_line_operator_config()
import src.models  # register foreign keys
import src.models.line_daily
import src.models.operator_registration
from src.api.deps import SessionLocal
from src.models.line_operator import LineOperatorMenuRelease
from src.models.master import User, VanzaiStaff
from src.models.operator_staff import LineStaffLink
from src.services import worker_schedule as ws
from src.services.line_operator_menu import MenuClient, MenuError, current_release, reconcile_all
from src.services.line_operator import identity, OperatorError
from src.services.audit import AuditService


def image_for(spec, labels):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (2500, 1686), "#eef3f6")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ROOT / "assets/fonts/ipaexg.ttf"), 76)
    small = ImageFont.truetype(str(ROOT / "assets/fonts/ipaexg.ttf"), 45)
    for index, area in enumerate(spec["areas"]):
        b = area["bounds"]
        x, y, width, height = (b[k] for k in ("x", "y", "width", "height"))
        color = "#164f40" if index == 0 else "#1c436c" if area["action"]["type"] == "richmenuswitch" else "#ffffff"
        draw.rounded_rectangle((x + 10, y + 10, x + width - 10, y + height - 10), radius=25, fill=color, outline="#b8cbd5", width=3)
        text_color = "white" if color != "#ffffff" else "#193c50"
        text = labels[index]
        selected_font = small if height < 300 else font
        lines = text.split("\n")
        total = len(lines) * (selected_font.size + 25)
        for line_index, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=selected_font)
            draw.text((x + (width - (bbox[2] - bbox[0])) / 2, y + (height - total) / 2 + line_index * (selected_font.size + 25)), line, font=selected_font, fill=text_color)
    buffer = BytesIO(); image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def operator_spec(liff_id, dual, worker_alias):
    actions = [("起床状況", "wake"), ("カレンダー", "calendar"), ("自分の\n登録情報", "profile")]
    areas, labels = [], []
    for i, (label, mode) in enumerate(actions):
        bounds = {"x": (i % 2) * 1250, "y": (i // 2) * 843, "width": 1250, "height": 843} if dual else {"x": i * 833, "y": 0, "width": 833, "height": 1686}
        areas.append({"bounds": bounds, "action": {"type": "uri", "uri": f"https://liff.line.me/{liff_id}?m={mode}"}})
        labels.append(label)
    if dual:
        areas.append({"bounds": {"x": 1250, "y": 843, "width": 1250, "height": 843}, "action": {"type": "richmenuswitch", "richMenuAliasId": worker_alias, "data": "op_menu:worker"}})
        labels.append("稼働者用へ\n切り替える")
    return {"size": {"width": 2500, "height": 1686}, "selected": True, "name": "VANZAI 運営メニュー", "chatBarText": "運営メニュー", "areas": areas}, labels


def worker_spec(default, operator_alias):
    # Copy the actual current menu's enabled actions instead of publishing disabled functions.
    areas = [{"bounds": {"x": 0, "y": 0, "width": 2500, "height": 220}, "action": {"type": "richmenuswitch", "richMenuAliasId": operator_alias, "data": "op_menu:operator"}}]
    labels = ["運営用メニューへ切り替える"]
    names = {"wk_wake": "起床報告", "wk_checkin": "出勤報告", "wk_checkout": "退勤報告", "wk_sales": "売上報告", "wk_orders": "発注依頼書", "wk_schedule": "スケジュール"}
    for source in default["areas"]:
        area = deepcopy(source)
        b = area["bounds"]
        scale_x = 2500 / default["size"]["width"]
        scale_y = 1466 / default["size"]["height"]
        area["bounds"] = {"x": round(b["x"] * scale_x), "y": 220 + round(b["y"] * scale_y), "width": int(b["width"] * scale_x), "height": int(b["height"] * scale_y)}
        action = area["action"]
        labels.append(names.get(action.get("data"), "発注依頼書" if "m=orders" in action.get("uri", "") else "スケジュール" if "m=home" in action.get("uri", "") else action.get("label", "確認する")))
        areas.append(area)
    return {"size": {"width": 2500, "height": 1686}, "selected": True, "name": "VANZAI 兼務者 稼働者メニュー", "chatBarText": "稼働者メニュー", "areas": areas}, labels


def worker_image(spec, labels, original):
    from PIL import Image
    image = Image.open(BytesIO(image_for({"areas": spec["areas"][:1]}, labels[:1])))
    with Image.open(BytesIO(original)) as source:
        image.paste(source.convert("RGB").resize((2500, 1466)), (0, 220))
    output = BytesIO(); image.save(output, format="PNG", optimize=True)
    data = output.getvalue()
    if len(data) > 1024 * 1024:
        raise RuntimeError("Worker menu image exceeds LINE size limit")
    return data


def publish(db, client):
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(261026530)"))
    if current_release(db):
        return {"published": True, "already_published": True}
    if db.query(LineOperatorMenuRelease.id).first():
        return {"published": False, "reason": "disabled_by_admin"}
    entry = operator_entry()
    if not entry["enabled"]:
        return {"published": False, "reason": "not_configured"}
    original = client.call("GET", "/user/all/richmenu")["richMenuId"]
    default = client.call("GET", f"/richmenu/{original}")
    default_image = client.content(original)
    tag = uuid.uuid4().hex[:10]
    aliases = {"operator_dual": f"vz-operator-{tag}", "worker_dual": f"vz-worker-{tag}"}
    specs = {"operator_only": operator_spec(entry["liff_id"], False, aliases["worker_dual"]), "operator_dual": operator_spec(entry["liff_id"], True, aliases["worker_dual"]), "worker_dual": worker_spec(default, aliases["operator_dual"])}
    menus, created_aliases = {}, []
    try:
        for kind, (spec, labels) in specs.items():
            mid = client.call("POST", "/richmenu", spec)["richMenuId"]
            menus[kind] = mid
            picture = worker_image(spec, labels, default_image) if kind == "worker_dual" else image_for(spec, labels)
            client.call("POST", f"/richmenu/{mid}/content", image=picture)
        for kind, alias in aliases.items():
            client.call("POST", "/richmenu/alias", {"richMenuAliasId": alias, "richMenuId": menus[kind]})
            created_aliases.append(alias)
        if client.call("GET", "/user/all/richmenu")["richMenuId"] != original:
            raise RuntimeError("Default menu changed during publication")
        db.add(LineOperatorMenuRelease(menus=menus, active=True, created_at=ws.now_utc(), created_by="deploy"))
        AuditService(db).log("operator_menus_published", actor="deploy", target_type="line_menu", after_value={"count": 3, "default_unchanged": True})
        db.commit()
    except Exception:
        db.rollback()
        for alias in created_aliases:
            try: client.call("DELETE", f"/richmenu/alias/{alias}")
            except MenuError: pass
        for mid in menus.values():
            try: client.call("DELETE", f"/richmenu/{mid}")
            except MenuError: pass
        raise
    return {"published": True, "created": 3, "default_unchanged": True}


def status(db):
    counts = {"operator_links": 0, "eligible": 0, "needs_login_mapping": 0}
    for link in db.query(LineStaffLink).filter_by(status="active").all():
        counts["operator_links"] += 1
        try: identity(db, link.line_user_id); counts["eligible"] += 1
        except OperatorError: counts["needs_login_mapping"] += 1
    return {**counts, "worker_role_users": db.query(User).filter_by(role="worker", is_active=True, deleted_at=None).count(), "menus_published": bool(current_release(db))}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=("publish", "sync", "status", "disable")); args = parser.parse_args()
    with SessionLocal() as db:
        if args.action == "publish":
            print(json.dumps(publish(db, MenuClient())))
            print(json.dumps(reconcile_all(db)))
        elif args.action == "sync": print(json.dumps(reconcile_all(db)))
        elif args.action == "disable":
            db.query(LineOperatorMenuRelease).update({"active": False})
            AuditService(db).log("operator_menus_disabled", actor="operator-menu-admin", target_type="line_menu")
            db.commit()
            print(json.dumps(reconcile_all(db)))
        print(json.dumps(status(db)))


if __name__ == "__main__":
    try: main()
    except MenuError as exc:
        print(json.dumps({"error": "LINE menu operation failed", "status": exc.status})); sys.exit(1)
