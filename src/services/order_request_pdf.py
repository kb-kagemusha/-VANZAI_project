"""発注依頼書PDF。

弁護士確認済み書式は未入手のため、入力項目を枠付きで並べる保存用PDFとする。
書式の欄位置へ合わせる作業は TEMPLATE_LAYOUT_APPLIED を真にするときだけ行う。
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.services.order_request_format import DOCUMENT_TITLE, parse_sections
from src.services.pdf_generator import DEFAULT_FONT

# 書式の入手と受託者名欄の対応が終わるまで偽のままにする。
TEMPLATE_LAYOUT_APPLIED = False

# 保存済みPDFを開いたとき、この印が無いものは項目枠の版へ作り直す。
PDF_LAYOUT_ID = "order-request-boxed-v1"

TEST_BANNER = "テスト・正式な発注ではありません"
LAYOUT_PENDING_BANNER = (
    "弁護士確認済み書式のレイアウトは未適用です。このPDFは入力内容の保存です。"
)
REPLY_NOTE = (
    "返事は本人の「依頼の案件、受諾します」または「今回は辞退します」で記録します。"
    "PDFを開いたことは返事ではありません。"
)

_INK = colors.HexColor("#1d2731")
_MUTED = colors.HexColor("#5c6b7a")
_LINE = colors.HexColor("#d0cbc6")
_LABEL_BG = colors.HexColor("#f6f4f1")
_PAPER = colors.HexColor("#f7f5f2")
_ACCENT = colors.HexColor("#c8553d")
_HEADER_BG = colors.HexColor("#1d2731")
_WARN = colors.HexColor("#8a1c1c")
_WARN_BG = colors.HexColor("#fdecec")
_WHITE = colors.white


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
    page_width, _page_height = A4
    left = 16 * mm
    right = 16 * mm
    content_width = page_width - left - right
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=DOCUMENT_TITLE if _is_template(request_conditions, body) else "発注依頼書",
        subject=PDF_LAYOUT_ID,
    )
    styles = _styles()
    story: list = []
    if kind == "test":
        story.append(_banner(TEST_BANNER, content_width, styles))
        story.append(Spacer(1, 3 * mm))

    title = DOCUMENT_TITLE if _is_template(request_conditions, body) else "発注依頼書"
    story.append(_header(title, document_number, version_no, content_width, styles))
    story.append(Spacer(1, 4 * mm))
    story.append(_field_table(_document_fields(
        request_conditions=request_conditions,
        body=body,
        work_date_label=work_date_label,
        site_name=site_name,
        site_address=site_address,
        contact_name=contact_name,
        contact_desk=contact_desk,
        counterparty_note=counterparty_note,
        worker_names=worker_names,
    ), content_width, styles))
    story.append(Spacer(1, 4 * mm))
    story.append(_note_box(REPLY_NOTE, content_width, styles))

    def _decorate(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_MUTED)
        canvas.setFont(DEFAULT_FONT, 8)
        canvas.drawString(left, 10 * mm, f"{document_number}　第{version_no}版")
        if not TEMPLATE_LAYOUT_APPLIED:
            canvas.drawString(left, 6 * mm, LAYOUT_PENDING_BANNER)
        canvas.restoreState()

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buffer.getvalue()


def _is_template(request_conditions: str, body: str) -> bool:
    return parse_sections(request_conditions) is not None or (body or "").startswith(DOCUMENT_TITLE)


def _document_fields(
    *,
    request_conditions: str,
    body: str,
    work_date_label: str,
    site_name: str,
    site_address: str | None,
    contact_name: str,
    contact_desk: str,
    counterparty_note: str | None,
    worker_names: list[str],
) -> list[tuple[str, str]]:
    extras = [
        ("担当者", contact_name or contact_desk or ""),
        ("取引相手メモ", counterparty_note or ""),
        ("送付先\n（確定時の氏名）", "、".join(worker_names)),
    ]
    if _is_template(request_conditions, body):
        document_body = body or ""
        if document_body.startswith(DOCUMENT_TITLE):
            document_body = document_body[len(DOCUMENT_TITLE):].lstrip("\n")
        fields = _headed_fields(document_body)
        if not fields:
            fields = [("本文", document_body)]
        present = {caption for caption, _text in fields}
        for caption, text in extras:
            if caption not in present:
                fields.append((caption, text))
        return fields
    return [
        ("日付", work_date_label),
        ("現場", site_name),
        ("現場住所", site_address or ""),
        ("依頼条件", request_conditions),
        ("本文", body),
        *extras,
    ]


def _headed_fields(document_body: str) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    caption: str | None = None
    lines: list[str] = []
    for raw in document_body.splitlines():
        stripped = raw.strip()
        if stripped.startswith("■"):
            if caption is not None:
                fields.append((caption, "\n".join(lines).strip()))
            caption = stripped[1:].strip().rstrip("：:").strip() or "項目"
            lines = []
            continue
        if caption is not None:
            lines.append(raw)
    if caption is not None:
        fields.append((caption, "\n".join(lines).strip()))
    return fields


def _styles() -> dict[str, ParagraphStyle]:
    common = {"fontName": DEFAULT_FONT, "wordWrap": "CJK"}
    return {
        "title": ParagraphStyle(
            "or_title",
            fontSize=16,
            leading=22,
            textColor=_WHITE,
            alignment=TA_LEFT,
            **common,
        ),
        "meta": ParagraphStyle(
            "or_meta",
            fontSize=9,
            leading=13,
            textColor=_INK,
            **common,
        ),
        "label": ParagraphStyle(
            "or_label",
            fontSize=9,
            leading=13,
            textColor=_MUTED,
            **common,
        ),
        "value": ParagraphStyle(
            "or_value",
            fontSize=11,
            leading=16,
            textColor=_INK,
            **common,
        ),
        "empty": ParagraphStyle(
            "or_empty",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#9aa6b2"),
            **common,
        ),
        "banner": ParagraphStyle(
            "or_banner",
            fontSize=11,
            leading=15,
            textColor=_WARN,
            **common,
        ),
        "note": ParagraphStyle(
            "or_note",
            fontSize=8.5,
            leading=12,
            textColor=_MUTED,
            **common,
        ),
    }


def _paragraph(text: str, style: ParagraphStyle, empty_style: ParagraphStyle | None = None) -> Paragraph:
    raw = (text or "").strip()
    if not raw and empty_style is not None:
        return Paragraph("—", empty_style)
    return Paragraph(escape(raw).replace("\n", "<br/>"), style)


def _header(title: str, document_number: str, version_no: int, width: float, styles: dict) -> Table:
    meta = f"文書番号　{document_number}　　第{version_no}版"
    table = Table(
        [
            [_paragraph(title, styles["title"])],
            [_paragraph(meta, styles["meta"])],
        ],
        colWidths=[width],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("BACKGROUND", (0, 1), (-1, 1), _PAPER),
        ("BOX", (0, 0), (-1, -1), 0.8, _HEADER_BG),
        ("LINEABOVE", (0, 1), (-1, 1), 2.5, _ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, 0), (0, 0), 8),
        ("TOPPADDING", (0, 1), (-1, 1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _field_table(fields: list[tuple[str, str]], width: float, styles: dict) -> Table:
    label_width = 32 * mm
    accent_width = 1.8 * mm
    value_width = width - label_width - accent_width
    rows = [
        [
            "",
            _paragraph(caption, styles["label"]),
            _paragraph(text, styles["value"], styles["empty"]),
        ]
        for caption, text in fields
    ]
    table = Table(rows, colWidths=[accent_width, label_width, value_width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), _ACCENT),
        ("BACKGROUND", (1, 0), (1, -1), _LABEL_BG),
        ("BACKGROUND", (2, 0), (2, -1), _WHITE),
        ("BOX", (0, 0), (-1, -1), 0.8, _LINE),
        ("LINEBEFORE", (1, 0), (1, -1), 0.4, _LINE),
        ("LINEBEFORE", (2, 0), (2, -1), 0.4, _LINE),
        ("LINEBELOW", (1, 0), (-1, -2), 0.4, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 6),
        ("RIGHTPADDING", (1, 0), (1, -1), 4),
        ("LEFTPADDING", (2, 0), (2, -1), 8),
        ("RIGHTPADDING", (2, 0), (2, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _banner(text: str, width: float, styles: dict) -> Table:
    table = Table([[_paragraph(text, styles["banner"])]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _WARN_BG),
        ("BOX", (0, 0), (-1, -1), 1, _WARN),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _note_box(text: str, width: float, styles: dict) -> Table:
    table = Table([[_paragraph(text, styles["note"])]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _PAPER),
        ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table
