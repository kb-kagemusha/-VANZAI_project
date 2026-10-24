"""A2 のリッチメニュー画像（2500x1686）を作る（0.50.0、DEC-084）。使い方: python scripts/line/rich_menu/make_a2.py
A1 と同じ絵柄で、⑤⑥の副文言をWeb確認画面に合わせる（⑤一覧を開く・⑥月間・7日分の予定）。押せる範囲は a2.json。
Noto Sans CJK（Linux の fonts-noto-cjk）が必要。
"""
import os
from PIL import Image, ImageDraw, ImageFont
S=2  # supersample
W,H=2500,1686
img=Image.new("RGB",(W*S,H*S),"#EEF1F4")
d=ImageDraw.Draw(img)
BOLD="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
MED="/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
def F(path,size): return ImageFont.truetype(path,size*S,index=0)
cols=[(0,833),(834,1667),(1667,2500)]
rows=[(0,843),(843,1686)]
panels=[
 ("wake","起床報告",None,"押して報告",True,"#F08C00"),
 ("in","出勤報告",None,"",False,None),
 ("out","退勤報告",None,"",False,None),
 ("sales","販売報告",None,"",False,None),
 ("doc","受託済みの","発注依頼書","一覧を開く",True,"#1C64F2"),
 ("cal","スケジュール","確認","月間・7日分の予定",True,"#0E9F6E"),
]
GAP=14
def s(v): return int(v*S)
DOC_LINE="#1C64F2"; DOC_FOLD="#A9C4FB"
def icon(kind,cx,cy,r,col):
    w=s(22)  # stroke
    if kind=="wake":
        R=r*0.52
        # bells
        for sx in (-1,1):
            bx=cx+sx*R*0.78; by=cy-R*0.82
            d.pieslice([bx-R*0.42,by-R*0.42,bx+R*0.42,by+R*0.42],180+ (0 if sx<0 else 0),360,fill=col)
        d.ellipse([cx-R,cy-R,cx+R,cy+R],outline=col,width=w)
        d.line([cx,cy,cx,cy-R*0.6],fill=col,width=w)
        d.line([cx,cy,cx+R*0.45,cy+R*0.25],fill=col,width=w)
        d.ellipse([cx-w*0.8,cy-w*0.8,cx+w*0.8,cy+w*0.8],fill=col)
        for sx in (-1,1):
            d.line([cx+sx*R*0.6,cy+R*0.8,cx+sx*R*0.85,cy+R*1.1],fill=col,width=w)
    elif kind in ("in","out"):
        R=r*0.55
        # door frame
        x0=cx-R*0.1; x1=cx+R*0.9; y0=cy-R; y1=cy+R
        d.rounded_rectangle([x0,y0,x1,y1],radius=s(10),outline=col,width=w)
        d.ellipse([x0+(x1-x0)*0.18-w*0.6,cy-w*0.6,x0+(x1-x0)*0.18+w*0.6,cy+w*0.6],fill=col)
        ax0,ax1=cx-R*1.05,cx+R*0.35
        if kind=="in":
            d.line([ax0,cy,ax1,cy],fill=col,width=w)
            d.polygon([(ax1+R*0.12,cy),(ax1-R*0.3,cy-R*0.32),(ax1-R*0.3,cy+R*0.32)],fill=col)
        else:
            d.line([ax0+R*0.3,cy,ax1,cy],fill=col,width=w)
            d.polygon([(ax0-R*0.05,cy),(ax0+R*0.37,cy-R*0.32),(ax0+R*0.37,cy+R*0.32)],fill=col)
    elif kind=="sales":
        R=r*0.55
        base=cy+R*0.85
        for i,h in enumerate((0.6,1.05,1.5)):
            x=cx-R*0.85+i*R*0.65
            d.rounded_rectangle([x,base-R*h,x+R*0.42,base],radius=s(6),fill=col)
        d.line([cx-R*1.0,base+w*0.6,cx+R*1.0,base+w*0.6],fill=col,width=w)
    elif kind=="doc":
        R=r*0.58
        x0,x1,y0,y1=cx-R*0.72,cx+R*0.72,cy-R,cy+R
        f=R*0.42
        d.polygon([(x0,y0),(x1-f,y0),(x1,y0+f),(x1,y1),(x0,y1)],fill=col)
        d.polygon([(x1-f,y0),(x1-f,y0+f),(x1,y0+f)],fill=DOC_FOLD)
        for i in range(3):
            y=y0+R*0.72+i*R*0.36
            d.line([x0+R*0.26,y,x1-R*0.26-(R*0.38 if i==2 else 0),y],fill=DOC_LINE,width=s(15))
    elif kind=="cal":
        R=r*0.58
        x0,x1,y0,y1=cx-R,cx+R,cy-R*0.8,cy+R
        d.rounded_rectangle([x0,y0,x1,y1],radius=s(16),outline=col,width=w)
        d.rectangle([x0,y0,x1,y0+R*0.42],fill=col)
        for sx in (-0.5,0.5):
            d.line([cx+sx*R,y0-R*0.25,cx+sx*R,y0+R*0.15],fill=col,width=w)
        for rr in range(2):
            for cc in range(3):
                gx=x0+R*0.45+cc*R*0.55; gy=y0+R*0.78+rr*R*0.48
                d.rounded_rectangle([gx-R*0.14,gy-R*0.12,gx+R*0.14,gy+R*0.12],radius=s(4),fill=col)
def center_text(text,font,cx,y,fill):
    b=d.textbbox((0,0),text,font=font)
    d.text((cx-(b[2]-b[0])/2-b[0],y-b[1]),text,font=font,fill=fill)
    return b[3]-b[1]
for i,(kind,l1,l2,cap,active,accent) in enumerate(panels):
    c=cols[i%3]; r=rows[i//3]
    x0,y0,x1,y1=s(c[0]+GAP),s(r[0]+GAP),s(c[1]-GAP),s(r[1]-GAP)
    if active:
        d.rounded_rectangle([x0+s(6),y0+s(10),x1+s(6),y1+s(10)],radius=s(40),fill="#D9DEE5")
        mask=Image.new("L",img.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([x0,y0,x1,y1],radius=s(40),fill=255)
        layer=Image.new("RGB",img.size,"#FFFFFF")
        ImageDraw.Draw(layer).rectangle([x0,y0,x1,y0+s(22)],fill=accent)
        img.paste(layer,(0,0),mask)
    else:
        d.rounded_rectangle([x0,y0,x1,y1],radius=s(40),fill="#E2E6EB")
    cx=(x0+x1)/2
    two=l2 is not None
    cy=y0+s(255 if two else 280)
    rad=s(150)
    if active:
        d.ellipse([cx-rad,cy-rad,cx+rad,cy+rad],fill=accent)
        icon(kind,cx,cy,rad,"#FFFFFF")
    else:
        d.ellipse([cx-rad,cy-rad,cx+rad,cy+rad],fill="#CDD2D9")
        icon(kind,cx,cy,rad,"#F4F5F7")
    tcol="#1F2937" if active else "#8A93A0"
    fs=96
    font=F(BOLD,fs)
    ty=cy+rad+s(55)
    h=center_text(l1,font,cx,ty,tcol)
    if two:
        ty+=h+s(22)
        h=center_text(l2,font,cx,ty,tcol)
    ty+=h+s(40 if active else 58)
    if active:
        center_text(cap,F(MED,52),cx,ty,"#6B7280")
    else:
        pf=F(BOLD,54); label="準備中"
        b=d.textbbox((0,0),label,font=pf); tw=b[2]-b[0]; th=b[3]-b[1]
        px,py=s(44),s(18)
        d.rounded_rectangle([cx-tw/2-px,ty-py,cx+tw/2+px,ty+th+py],radius=s(40),fill="#7B8491")
        center_text(label,pf,cx,ty,"#FFFFFF")
out=img.resize((W,H),Image.LANCZOS)
path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"a2.png")
out.save(path,optimize=True)
print(path, os.path.getsize(path))
