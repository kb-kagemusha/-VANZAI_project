"""公式LINEの稼働者用リッチメニューを公開する（DEC-064、A1）。

使い方（VPSで、.env を読み込んだシェルから）:
  python scripts/line/rich_menu.py status
  python scripts/line/rich_menu.py apply --stage a1 --image /path/to/menu.png --by kb

apply は次を順に行い、最後に公開記録（line_rich_menu_releases）を残す。
  1. scripts/line/rich_menu/<stage>.json からリッチメニューを作る
  2. 画像をアップロードする（2500x1686 の PNG/JPEG、1MB 以下）
  3. 全員の既定メニューにする
公開記録の enabled_actions が、Webhookで「押してよい機能」の正本になる。
途中で失敗したときは公開記録を残さない（Webhook側の有効な機能は変わらない）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

API = "https://api.line.me/v2/bot"
DATA_API = "https://api-data.line.me/v2/bot"
MAX_IMAGE_BYTES = 1024 * 1024
MENU_ACTIONS = {"wk_wake", "wk_checkin", "wk_checkout", "wk_sales", "wk_orders", "wk_schedule"}
# 押せる範囲を持たない業務機能（統合計画 §3、R-02）。Web側のAPIも公開記録のこのキーで判定する。
FEATURE_ACTIONS = {"pick_dates", "web_home", "web_orders", "change_request"}
KNOWN_ACTIONS = MENU_ACTIONS | FEATURE_ACTIONS


def _token() -> str:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("LINE_CHANNEL_ACCESS_TOKEN がありません。.env を読み込んでから実行してください。")
    return token


def _call(method: str, url: str, *, body: bytes | None = None, content_type: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {_token()}"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        sys.exit(f"LINE API エラー {exc.code}: {method} {url}\n{detail}")


def _image_size(data: bytes) -> tuple[str, int, int]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", width, height
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return "image/jpeg", width, height
            length = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + length
    sys.exit("画像は PNG か JPEG にしてください。")


def load_stage(stage: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "rich_menu", f"{stage}.json")
    if not os.path.exists(path):
        sys.exit(f"{path} がありません。")
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    actions = set(spec["enabled_actions"])
    unknown = actions - KNOWN_ACTIONS
    if unknown:
        sys.exit(f"未知の機能: {sorted(unknown)}")
    area_actions = set()
    for area in spec["rich_menu"]["areas"]:
        action = area["action"]
        if action.get("type") == "postback":
            area_actions.add(action["data"])
        elif action.get("type") == "uri":
            # Web画面を直接開く範囲。対応する業務機能（web_home 等）を enabled_actions に入れて公開を管理する
            if not str(action.get("uri", "")).startswith("https://liff.line.me/"):
                sys.exit(f"URIの範囲は LIFF のURLだけにしてください: {action.get('uri')}")
        else:
            sys.exit(f"未対応の押せる範囲: {action.get('type')}")
    menu_actions = actions & MENU_ACTIONS
    if area_actions != menu_actions:
        sys.exit(f"押せる範囲 {sorted(area_actions)} と enabled_actions のメニュー機能 {sorted(menu_actions)} が一致しません。")
    return spec


def cmd_status(_args) -> None:
    from src.api.deps import SessionLocal
    from src.models.line_daily import LineRichMenuRelease

    default = _call("GET", f"{API}/user/all/richmenu")
    print(f"LINE上の既定メニュー: {default.get('richMenuId', '(なし)')}")
    db = SessionLocal()
    try:
        latest = db.query(LineRichMenuRelease).order_by(LineRichMenuRelease.applied_at.desc()).first()
        if latest is None:
            print("公開記録: なし（Webhookではどの機能も使えない状態）")
        else:
            print(f"公開記録: stage={latest.stage} menu={latest.rich_menu_id} actions={latest.enabled_actions} at={latest.applied_at.isoformat()} by={latest.applied_by}")
            if latest.rich_menu_id != default.get("richMenuId"):
                print("注意: LINE上の既定メニューと公開記録が一致しません。")
    finally:
        db.close()


def cmd_apply(args) -> None:
    from src.api.deps import SessionLocal
    from src.models.base import generate_ulid
    from src.models.line_daily import LineRichMenuRelease

    spec = load_stage(args.stage)
    with open(args.image, "rb") as fh:
        image = fh.read()
    if len(image) > MAX_IMAGE_BYTES:
        sys.exit("画像は1MB以下にしてください。")
    content_type, width, height = _image_size(image)
    size = spec["rich_menu"]["size"]
    if (width, height) != (size["width"], size["height"]):
        sys.exit(f"画像のサイズ {width}x{height} がメニュー定義 {size['width']}x{size['height']} と違います。")

    created = _call("POST", f"{API}/richmenu", body=json.dumps(spec["rich_menu"]).encode("utf-8"), content_type="application/json")
    menu_id = created["richMenuId"]
    print(f"作成: {menu_id}")
    _call("POST", f"{DATA_API}/richmenu/{menu_id}/content", body=image, content_type=content_type)
    print("画像をアップロードしました")
    _call("POST", f"{API}/user/all/richmenu/{menu_id}")
    print("全員の既定メニューにしました")

    db = SessionLocal()
    try:
        db.add(
            LineRichMenuRelease(
                id=generate_ulid(),
                stage=args.stage,
                rich_menu_id=menu_id,
                enabled_actions=sorted(spec["enabled_actions"]),
                image_sha256=hashlib.sha256(image).hexdigest(),
                applied_at=datetime.now(timezone.utc),
                applied_by=(args.by or "cli")[:64],
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        print(f"公開記録を残せませんでした。LINE上は {menu_id} が既定です。もう一度 apply してください。", file=sys.stderr)
        raise
    finally:
        db.close()
    print(f"公開記録を残しました（有効な機能: {', '.join(sorted(spec['enabled_actions']))}）")


def cmd_features(args) -> None:
    """メニューの画像・押せる範囲を変えずに、業務機能だけを公開・停止する（統合計画 R-02）。新しい公開記録を追記する。"""
    from src.api.deps import SessionLocal
    from src.models.base import generate_ulid
    from src.models.line_daily import LineRichMenuRelease

    enable = set(args.enable or [])
    disable = set(args.disable or [])
    unknown = (enable | disable) - FEATURE_ACTIONS
    if unknown:
        sys.exit(f"業務機能のキーだけ切り替えられます。未知: {sorted(unknown)}（使えるキー: {sorted(FEATURE_ACTIONS)}）")
    db = SessionLocal()
    try:
        latest = db.query(LineRichMenuRelease).order_by(LineRichMenuRelease.applied_at.desc()).first()
        if latest is None:
            sys.exit("公開記録がありません。先に apply でメニューを公開してください。")
        actions = (set(latest.enabled_actions) | enable) - disable
        db.add(
            LineRichMenuRelease(
                id=generate_ulid(),
                stage=latest.stage,
                rich_menu_id=latest.rich_menu_id,
                enabled_actions=sorted(actions),
                image_sha256=latest.image_sha256,
                applied_at=datetime.now(timezone.utc),
                applied_by=(args.by or "cli")[:64],
            )
        )
        db.commit()
        print(f"有効な機能: {', '.join(sorted(actions))}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    apply = sub.add_parser("apply")
    apply.add_argument("--stage", required=True)
    apply.add_argument("--image", required=True)
    apply.add_argument("--by", default="")
    sub.add_parser("check").add_argument("--stage", required=True)
    features = sub.add_parser("features")
    features.add_argument("--enable", nargs="*")
    features.add_argument("--disable", nargs="*")
    features.add_argument("--by", default="")
    args = parser.parse_args()
    if args.command == "status":
        cmd_status(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "features":
        cmd_features(args)
    else:
        spec = load_stage(args.stage)
        print(f"OK: {args.stage} {sorted(spec['enabled_actions'])}")


if __name__ == "__main__":
    main()
