"""運営用リッチメニューの画像（2500x1686）を作る（0.53.8、DEC-125）。使い方: python scripts/line/rich_menu/make_operator.py
稼働者メニュー（make_a2.py）と同じ絵柄で6分割。色は同じ領域を同じ色にそろえる（起床=オレンジ、依頼書=青、予定=緑）。
operator_dual.png（兼務者：6つ目が稼働者メニューへの切替）と operator_only.png（運営専任：6つ目は空き枠）を作る。
押せる範囲は scripts/line/operator_menu.py の operator_spec。Noto Sans CJK（Linux の fonts-noto-cjk）が必要。
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 2  # supersample
W, H = 2500, 1686
BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
MED = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc" if not os.path.exists("/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc") else "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
COLS = [(0, 833), (834, 1667), (1667, 2500)]
ROWS = [(0, 843), (843, 1686)]
GAP = 14
ORANGE, GREEN, TEAL, BLUE, PURPLE, NAVY = "#F08C00", "#0E9F6E", "#057A55", "#1C64F2", "#7E3AF2", "#1C436C"
DOC_FOLD = "#A9C4FB"

PANELS_BASE = [
    ("wake", ["起床状況"], "未報告と連絡", ORANGE),
    ("today", ["今日の案件"], "参加予定者", GREEN),
    ("cal", ["案件", "カレンダー"], "1か月分", TEAL),
    ("doc", ["発注依頼書"], "受領状況・PDF", BLUE),
    ("avail", ["出勤可否", "配置"], "稼働者ごと", PURPLE),
]
SWITCH = ("switch", ["稼働者", "メニューへ"], "切り替える", NAVY)


def s(v):
    return int(v * S)


def F(path, size):
    return ImageFont.truetype(path, size * S, index=0)


def draw_menu(panels, path):
    img = Image.new("RGB", (W * S, H * S), "#EEF1F4")
    d = ImageDraw.Draw(img)

    def icon(kind, cx, cy, r, col, accent):
        w = s(22)
        if kind == "wake":
            R = r * 0.52
            for sx in (-1, 1):
                bx = cx + sx * R * 0.78; by = cy - R * 0.82
                d.pieslice([bx - R * 0.42, by - R * 0.42, bx + R * 0.42, by + R * 0.42], 180, 360, fill=col)
            d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=col, width=w)
            d.line([cx, cy, cx, cy - R * 0.6], fill=col, width=w)
            d.line([cx, cy, cx + R * 0.45, cy + R * 0.25], fill=col, width=w)
            d.ellipse([cx - w * 0.8, cy - w * 0.8, cx + w * 0.8, cy + w * 0.8], fill=col)
            for sx in (-1, 1):
                d.line([cx + sx * R * 0.6, cy + R * 0.8, cx + sx * R * 0.85, cy + R * 1.1], fill=col, width=w)
        elif kind in ("cal", "today"):
            R = r * 0.58
            x0, x1, y0, y1 = cx - R, cx + R, cy - R * 0.8, cy + R
            d.rounded_rectangle([x0, y0, x1, y1], radius=s(16), outline=col, width=w)
            d.rectangle([x0, y0, x1, y0 + R * 0.42], fill=col)
            for sx in (-0.5, 0.5):
                d.line([cx + sx * R, y0 - R * 0.25, cx + sx * R, y0 + R * 0.15], fill=col, width=w)
            if kind == "cal":
                for rr in range(2):
                    for cc in range(3):
                        gx = x0 + R * 0.45 + cc * R * 0.55; gy = y0 + R * 0.78 + rr * R * 0.48
                        d.rounded_rectangle([gx - R * 0.14, gy - R * 0.12, gx + R * 0.14, gy + R * 0.12], radius=s(4), fill=col)
            else:
                # 今日：1日だけ大きく塗る
                gx, gy = cx, y0 + R * 1.05
                d.rounded_rectangle([gx - R * 0.42, gy - R * 0.36, gx + R * 0.42, gy + R * 0.36], radius=s(10), fill=col)
                d.ellipse([gx - R * 0.14, gy - R * 0.14, gx + R * 0.14, gy + R * 0.14], fill=accent)
        elif kind == "doc":
            R = r * 0.58
            x0, x1, y0, y1 = cx - R * 0.72, cx + R * 0.72, cy - R, cy + R
            f = R * 0.42
            d.polygon([(x0, y0), (x1 - f, y0), (x1, y0 + f), (x1, y1), (x0, y1)], fill=col)
            d.polygon([(x1 - f, y0), (x1 - f, y0 + f), (x1, y0 + f)], fill=DOC_FOLD)
            # 受領のチェック
            d.line([x0 + R * 0.28, cy + R * 0.12, cx - R * 0.08, cy + R * 0.48, x1 - R * 0.22, cy - R * 0.3], fill=accent, width=s(18), joint="curve")
        elif kind == "avail":
            R = r * 0.55
            hx, hy = cx - R * 0.15, cy - R * 0.45
            d.ellipse([hx - R * 0.38, hy - R * 0.38, hx + R * 0.38, hy + R * 0.38], fill=col)
            d.pieslice([hx - R * 0.8, cy + R * 0.05, hx + R * 0.8, cy + R * 1.6], 180, 360, fill=col)
            bx, by = cx + R * 0.72, cy + R * 0.55
            d.ellipse([bx - R * 0.42, by - R * 0.42, bx + R * 0.42, by + R * 0.42], fill=col, outline=accent, width=s(10))
            d.line([bx - R * 0.2, by, bx - R * 0.04, by + R * 0.17, bx + R * 0.22, by - R * 0.17], fill=accent, width=s(12), joint="curve")
        elif kind == "switch":
            R = r * 0.55
            for direction in (1, -1):
                y = cy - R * 0.35 * direction
                x_from, x_to = (cx - R * 0.95, cx + R * 0.55) if direction == 1 else (cx + R * 0.95, cx - R * 0.55)
                d.line([x_from, y, x_to, y], fill=col, width=w)
                tip = x_to + direction * R * 0.4
                d.polygon([(tip, y), (x_to - direction * R * 0.02, y - R * 0.32), (x_to - direction * R * 0.02, y + R * 0.32)], fill=col)

    def center_text(text, font, cx, y, fill):
        b = d.textbbox((0, 0), text, font=font)
        d.text((cx - (b[2] - b[0]) / 2 - b[0], y - b[1]), text, font=font, fill=fill)
        return b[3] - b[1]

    for i in range(6):
        c = COLS[i % 3]; r = ROWS[i // 3]
        x0, y0, x1, y1 = s(c[0] + GAP), s(r[0] + GAP), s(c[1] - GAP), s(r[1] - GAP)
        if i >= len(panels):
            d.rounded_rectangle([x0, y0, x1, y1], radius=s(40), fill="#E2E6EB")
            continue
        kind, lines, cap, accent = panels[i]
        d.rounded_rectangle([x0 + s(6), y0 + s(10), x1 + s(6), y1 + s(10)], radius=s(40), fill="#D9DEE5")
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([x0, y0, x1, y1], radius=s(40), fill=255)
        layer = Image.new("RGB", img.size, "#FFFFFF")
        ImageDraw.Draw(layer).rectangle([x0, y0, x1, y0 + s(22)], fill=accent)
        img.paste(layer, (0, 0), mask)
        cx = (x0 + x1) / 2
        two = len(lines) > 1
        cy = y0 + s(255 if two else 280)
        rad = s(150)
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=accent)
        icon(kind, cx, cy, rad, "#FFFFFF", accent)
        ty = cy + rad + s(55)
        for index, line in enumerate(lines):
            size = 96
            while size > 60 and d.textbbox((0, 0), line, font=F(BOLD, size))[2] > (x1 - x0) - s(70):
                size -= 4
            h = center_text(line, F(BOLD, size), cx, ty, "#1F2937")
            ty += h + s(22 if index < len(lines) - 1 else 40)
        center_text(cap, F(MED, 52), cx, ty, "#6B7280")
    out = img.resize((W, H), Image.LANCZOS)
    out.save(path, optimize=True)
    return path, os.path.getsize(path)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    print(draw_menu(PANELS_BASE + [SWITCH], os.path.join(here, "operator_dual.png")))
    print(draw_menu(PANELS_BASE, os.path.join(here, "operator_only.png")))
