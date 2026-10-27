"""Draw the dual-role worker menu at its actual tile sizes, without image warping."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
S = 2
COLORS = ["#F08C00", "#0E9F6E", "#057A55", "#7E3AF2", "#1C64F2", "#0E9F6E"]
TITLES = [["起床報告"], ["出勤報告"], ["退勤報告"], ["販売報告"], ["受託済みの", "発注依頼書"], ["スケジュール", "確認"]]
CAPTIONS = ["押して報告", "押して報告", "押して報告", "押して報告", "一覧を開く", "月間・7日分の予定"]


def _font(size):
    for path in (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"), ROOT / "assets/fonts/ipaexg.ttf"):
        if path.exists():
            return ImageFont.truetype(str(path), int(size * S))
    raise RuntimeError("Japanese menu font missing")


def _icon(draw, kind, cx, cy, radius):
    """All coordinates share one scale, so circles and glyph proportions stay natural."""
    r, w = radius, 17 * S
    color = "#FFFFFF"
    if kind == 0:
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color, width=w)
        draw.line((cx, cy-r*.65, cx, cy, cx+r*.52, cy+r*.22), fill=color, width=w, joint="curve")
        for direction in (-1, 1):
            x, y = cx + direction*r*.85, cy-r*.9
            draw.pieslice((x-r*.4,y-r*.3,x+r*.4,y+r*.3),180,360,fill=color)
    elif kind in (1, 2):
        draw.line((cx-r*.25,cy-r,cx+r*.75,cy-r,cx+r*.75,cy+r,cx-r*.25,cy+r),fill=color,width=w)
        direction = 1 if kind == 1 else -1
        draw.line((cx-r,cy,cx+r*.3,cy),fill=color,width=w)
        tip = cx+r*.3 if direction == 1 else cx-r
        draw.polygon([(tip,cy),(tip-direction*r*.45,cy-r*.4),(tip-direction*r*.45,cy+r*.4)],fill=color)
    elif kind == 3:
        for index, height in enumerate((.65, 1.15, 1.65)):
            x = cx-r+index*r*.7
            draw.rounded_rectangle((x,cy+r-r*height,x+r*.45,cy+r),radius=5*S,fill=color)
    elif kind == 4:
        draw.rounded_rectangle((cx-r*.75,cy-r,cx+r*.75,cy+r),radius=8*S,fill=color)
        for index in range(3):
            y = cy-r*.45+index*r*.45
            draw.line((cx-r*.4,y,cx+r*.4,y),fill="#1C64F2",width=10*S)
    else:
        draw.rounded_rectangle((cx-r,cy-r*.8,cx+r,cy+r),radius=12*S,outline=color,width=w)
        draw.rectangle((cx-r,cy-r*.8,cx+r,cy-r*.3),fill=color)
        for row in range(2):
            for col in range(3):
                x,y = cx-r*.6+col*r*.6,cy+r*.1+row*r*.5
                draw.rectangle((x-r*.13,y-r*.12,x+r*.13,y+r*.12),fill=color)


def render(spec, labels):
    image = Image.new("RGB", (2500*S, 1686*S), "#EEF1F4")
    draw = ImageDraw.Draw(image)

    def text(value, y, cx, size, color, max_width=760):
        while size > 42 and draw.textbbox((0,0),value,font=_font(size))[2] > max_width*S:
            size -= 2
        font = _font(size)
        box = draw.textbbox((0,0),value,font=font)
        draw.text((cx-(box[2]-box[0])/2-box[0],y-box[1]),value,font=font,fill=color)
        return box[3]-box[1]

    switch = spec["areas"][0]["bounds"]
    draw.rounded_rectangle((14*S,14*S,2486*S,(switch["height"]-10)*S),radius=28*S,fill="#1C436C")
    text("運営メニューへ切り替える　→", 66*S, 1250*S, 70, "white", 2300)
    active = {}
    for area, label in zip(spec["areas"][1:], labels[1:]):
        bounds = area["bounds"]
        col = min(2, int((bounds["x"] + bounds["width"]/2) * 3 / 2500))
        row = min(1, int((bounds["y"] - 220 + bounds["height"]/2) * 2 / 1466))
        active[row*3+col] = (bounds, label)
    for index in range(6):
        col, row = index % 3, index // 3
        bounds = active[index][0] if index in active else {"x": (0,834,1667)[col], "y": 220+row*733, "width": 833, "height": 733}
        x,y,width,height = (bounds[k]*S for k in ("x","y","width","height"))
        enabled = index in active
        accent = COLORS[index] if enabled else "#9DA5B0"
        draw.rounded_rectangle((x+14*S,y+14*S,x+width-14*S,y+height-14*S),radius=36*S,fill="white" if enabled else "#E2E6EB")
        if enabled:
            draw.rounded_rectangle((x+38*S,y+14*S,x+width-38*S,y+30*S),radius=8*S,fill=accent)
        cx, cy, radius = x+width/2, y+207*S, 120*S
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill=accent)
        _icon(draw,index,cx,cy,radius*.57)
        lines = TITLES[index]
        # Preserve custom enabled-action labels rather than claiming another action.
        label = active.get(index, ({}, ""))[1]
        if enabled and label not in ("起床報告","出勤報告","退勤報告","売上報告","発注依頼書","スケジュール","スケジュール確認","受託済みの発注依頼書"):
            lines = [label]
        ty = y+375*S
        for line in lines:
            ty += text(line,ty,cx,82,"#1F2937" if enabled else "#8A93A0",width/S-70) + 16*S
        caption = CAPTIONS[index] if enabled else "準備中"
        text(caption,y+height-120*S,cx,48,"#6B7280",width/S-80)
    result = BytesIO()
    image.resize((2500,1686), Image.Resampling.LANCZOS).save(result,format="PNG",optimize=True)
    return result.getvalue()
