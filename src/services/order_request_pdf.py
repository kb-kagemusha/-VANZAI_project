"""発注依頼書PDF。

弁護士確認済み書式は未入手のため、入力スナップショットを縦に並べる保存用PDFとする。
書式の欄位置へ合わせる作業は TEMPLATE_LAYOUT_APPLIED を真にするときだけ行う。
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from src.services.order_request_format import DOCUMENT_TITLE, parse_sections
from src.services.pdf_generator import DEFAULT_FONT

# 書式の入手と受託者名欄の対応が終わるまで偽のままにする。
TEMPLATE_LAYOUT_APPLIED = False

TEST_BANNER = "テスト・正式な発注ではありません"
LAYOUT_PENDING_BANNER = (
    "弁護士確認済み書式のレイアウトは未適用です。このPDFは入力内容の保存です。"
)


def render_order_request_pdf(
    *,
    document_number: str,
    version_no: int,
    kind: str,
    work_date_label: str,
    site_name: str,
    site_address: str | None,
    request_conditions: str,
    body: str,
    contact_name: str,
    contact_desk: str,
    counterparty_note: str | None,
    worker_names: list[str],
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    title = ParagraphStyle(
        "or_title",
        fontName=DEFAULT_FONT,
        fontSize=16,
        leading=22,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#1d2731"),
        spaceAfter=8,
    )
    banner = ParagraphStyle(
        "or_banner",
        fontName=DEFAULT_FONT,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#8a1c1c"),
        spaceAfter=8,
    )
    label = ParagraphStyle(
        "or_label",
        fontName=DEFAULT_FONT,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#5c6b7a"),
        spaceBefore=8,
    )
    value = ParagraphStyle(
        "or_value",
        fontName=DEFAULT_FONT,
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#1d2731"),
    )

    story: list = []
    if kind == "test":
        story.append(Paragraph(escape(TEST_BANNER), banner))
    if not TEMPLATE_LAYOUT_APPLIED:
        story.append(Paragraph(escape(LAYOUT_PENDING_BANNER), banner))
    story.append(Paragraph(escape(f"{document_number}　第{version_no}版"), value))
    template = parse_sections(request_conditions) is not None or (body or "").startswith(DOCUMENT_TITLE)
    if template:
        story.append(Paragraph(escape(DOCUMENT_TITLE), title))
        document_body = body or ""
        if document_body.startswith(DOCUMENT_TITLE):
            document_body = document_body[len(DOCUMENT_TITLE):].lstrip("\n")
        story.append(Paragraph(escape(document_body).replace("\n", "<br/>"), value))
        fields = [
            ("担当者", contact_name),
            ("業務用窓口", contact_desk),
            ("取引相手メモ", counterparty_note or ""),
            ("送付先（確定時の氏名）", "、".join(worker_names)),
        ]
    else:
        story.append(Paragraph("発注依頼書", title))
        fields = [
            ("日付", work_date_label),
            ("現場", site_name),
            ("現場住所", site_address or ""),
            ("依頼条件", request_conditions),
            ("本文", body),
            ("担当者", contact_name),
            ("業務用窓口", contact_desk),
            ("取引相手メモ", counterparty_note or ""),
            ("送付先（確定時の氏名）", "、".join(worker_names)),
        ]
    for caption, text in fields:
        story.append(Paragraph(escape(caption), label))
        story.append(Paragraph(escape(text).replace("\n", "<br/>"), value))
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "受領は本人の「受け取りました」操作で記録します。このPDFを開いたことは受領ではありません。",
            label,
        )
    )
    doc.build(story)
    return buffer.getvalue()
