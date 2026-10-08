"""発注依頼書PDF。

弁護士確認済み書式は未入手のため、入力項目を枠付きで並べる保存用PDFとする。
書式の欄位置へ合わせる作業は TEMPLATE_LAYOUT_APPLIED を真にするときだけ行う。
"""
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.services.order_request_format import DOCUMENT_TITLE, parse_sections
from src.services.pdf_generator import DEFAULT_FONT

# 書式の入手と受託者名欄の対応が終わるまで偽のままにする。
TEMPLATE_LAYOUT_APPLIED = False

# 保存済みPDFを開いたとき、この印が無いものは作り直す（返事は本文の直後。複数人の氏名は出さない）。
PDF_LAYOUT_ID = "order-request-branded-v8"
NEW_HEADING = "【新規発注依頼】"
CHANGE_HEADING = "【発注依頼の変更】"
CANCEL_HEADING = "【発注済み依頼のキャンセル】"
CHANGE_NOTE = "＊赤文字が前回からの変更部分です"
_JST = ZoneInfo("Asia/Tokyo")
COMPANY_NAME = "株式会社VANZAI"
_LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "brand" / "vanzai-logo.png"

TEST_BANNER = "テスト・正式な発注ではありません"
REPLY_NOTE = (
    "返事は本人の「依頼の案件、受諾します」または「今回は辞退します」で記録します。"
    "PDFを開いたことは返事ではありません。"
)

_BRAND_RED = colors.HexColor("#E61F19")
_INK = colors.HexColor("#111111")
_MUTED = colors.HexColor("#5E5856")
_LINE = colors.HexColor("#E4D6D4")
_LABEL_BG = colors.HexColor("#FBF4F3")
_PAPER = colors.HexColor("#FBF7F6")
_ACCENT = _BRAND_RED
_WARN = _BRAND_RED
_WARN_BG = colors.HexColor("#FDECEB")
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
    created_at: datetime | None = None,
    notice: str = "new",
    previous_work_date_label: str = "",
    previous_site_name: str = "",
    previous_site_address: str | None = None,
    previous_request_conditions: str = "",
    previous_body: str = "",
    previous_contact_name: str = "",
    previous_contact_desk: str = "",
    previous_counterparty_note: str | None = None,
) -> bytes:
    buffer = BytesIO()
    page_width, _page_height = A4
    left = 16 * mm
    right = 16 * mm
    content_width = page_width - left - right
    styles = _styles()
    project_name = project_name_from_document(request_conditions, body)
    fields = _document_fields(
        request_conditions=request_conditions,
        body=body,
        work_date_label=work_date_label,
        site_name=site_name,
        site_address=site_address,
        contact_name=contact_name,
        contact_desk=contact_desk,
        counterparty_note=counterparty_note,
        worker_names=worker_names,
    )
    changed: set[str] = set()
    if notice == "change":
        previous_fields = _document_fields(
            request_conditions=previous_request_conditions,
            body=previous_body,
            work_date_label=previous_work_date_label,
            site_name=previous_site_name,
            site_address=previous_site_address,
            contact_name=previous_contact_name,
            contact_desk=previous_contact_desk,
            counterparty_note=previous_counterparty_note,
            worker_names=[],
        )
        changed = changed_field_captions(fields, previous_fields)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=_download_stem(work_date_label, project_name),
        subject=PDF_LAYOUT_ID,
    )
    story: list = []
    if kind == "test":
        story.append(_banner(TEST_BANNER, content_width, styles))
        story.append(Spacer(1, 3 * mm))

    if not _is_template(request_conditions, body):
        title_markup = "発注依頼書"
        notice_for_title = "new"
    else:
        title_markup = _title_markup(
            notice=notice,
            work_date_label=work_date_label,
            project_name=project_name,
            previous_work_date_label=previous_work_date_label,
            previous_project_name=project_name_from_document(previous_request_conditions, previous_body),
        )
        notice_for_title = notice
    story.append(_brand(content_width))
    story.append(Spacer(1, 4 * mm))
    story.extend(_title_block(
        title_markup,
        document_number,
        version_no,
        format_created_on(created_at),
        content_width,
        styles,
        notice=notice_for_title,
    ))
    story.append(_field_table(fields, content_width, styles, changed))
    story.append(Spacer(1, 3 * mm))
    story.append(_reply_note(content_width, styles))
    def _decorate(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_INK)
        canvas.setFont(DEFAULT_FONT, 8)
        canvas.drawRightString(page_width - right, 6 * mm, COMPANY_NAME)
        canvas.setFillColor(_MUTED)
        canvas.drawString(left, 6 * mm, f"{document_number}　第{version_no}版")
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
    # 送付先の氏名はPDFに出さない。1通を複数人へ送ると、他の人の名前が渡る。
    del worker_names
    extras = [
        ("担当者", contact_name or contact_desk or ""),
        ("取引相手メモ", counterparty_note or ""),
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
            fontSize=18,
            leading=24,
            textColor=_INK,
            alignment=TA_CENTER,
            **common,
        ),
        "company": ParagraphStyle(
            "or_company",
            fontSize=12,
            leading=16,
            textColor=_INK,
            alignment=TA_RIGHT,
            **common,
        ),
        "meta": ParagraphStyle(
            "or_meta",
            fontSize=9,
            leading=14,
            textColor=_INK,
            alignment=TA_RIGHT,
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
            leading=11.5,
            textColor=_MUTED,
            **common,
        ),
        "value_changed": ParagraphStyle(
            "or_value_changed",
            fontSize=11,
            leading=16,
            textColor=_BRAND_RED,
            **common,
        ),
        "change_note": ParagraphStyle(
            "or_change_note",
            fontSize=8,
            leading=11,
            textColor=_BRAND_RED,
            **common,
        ),
    }


def _paragraph(text: str, style: ParagraphStyle, empty_style: ParagraphStyle | None = None) -> Paragraph:
    raw = (text or "").strip()
    if not raw and empty_style is not None:
        return Paragraph("—", empty_style)
    return Paragraph(escape(raw).replace("\n", "<br/>"), style)


def format_created_on(value: datetime | None) -> str:
    moment = value or datetime.now(_JST)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    local = moment.astimezone(_JST)
    return f"{local.year}年{local.month}月{local.day}日"


def _title_block(
    title_markup: str,
    document_number: str,
    version_no: int,
    created_label: str,
    width: float,
    styles: dict,
    *,
    notice: str,
) -> list:
    heading = Table([[Paragraph(title_markup, styles["title"])]], colWidths=[width])
    heading.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    number = Paragraph(f"文書番号　{escape(document_number)}　第{version_no}版", styles["meta"])
    created = Paragraph(f"作成日　{escape(created_label)}", styles["meta"])
    note = Paragraph(CHANGE_NOTE if notice == "change" else "", styles["change_note"])
    meta = Table(
        [[number, ""], [note, created]],
        colWidths=[width * 0.62, width * 0.38],
    )
    meta.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("ALIGN", (0, 0), (1, 0), "RIGHT"),
        ("ALIGN", (1, 1), (1, 1), "RIGHT"),
        ("ALIGN", (0, 1), (0, 1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return [heading, Spacer(1, 1.5 * mm), meta, Spacer(1, 3.5 * mm)]


def _brand(width: float) -> Table:
    logo_height = 11 * mm
    logo_width = logo_height * (200 / 50)
    logo = Image(str(_LOGO_PATH), width=logo_width, height=logo_height, mask="auto")
    company = Paragraph(escape(COMPANY_NAME), _styles()["company"])
    table = Table([[logo, company]], colWidths=[logo_width + 4 * mm, width - logo_width - 4 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 2.4, _ACCENT),
    ]))
    return table


def project_name_from_document(request_conditions: str | None, body: str | None) -> str:
    sections = parse_sections(request_conditions)
    if sections:
        name = str(sections.get("project_name") or "").strip()
        if name:
            return name.splitlines()[0].strip()
    for caption, text in _headed_fields(body or ""):
        if caption == "案件名" and text.strip():
            return text.strip().splitlines()[0].strip()
    return ""


def order_request_document_title(*, work_date_label: str, project_name: str, notice: str = "new") -> str:
    """PDFの見出し。1行目が依頼の種類、2行目が稼働日：案件名。"""
    line = _compose_title(_plain_piece(work_date_label), _display_project_name(project_name), empty="")
    head = {"change": CHANGE_HEADING, "cancel": CANCEL_HEADING}.get(notice, NEW_HEADING)
    return f"{head}\n{line}" if line else head


def order_request_pdf_filename(*, work_date_label: str, project_name: str) -> str:
    return f"{_download_stem(work_date_label, project_name)}.pdf"


def attachment_content_disposition(filename: str) -> str:
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"order-request.pdf\"; filename*=UTF-8''{encoded}"


def _download_stem(work_date_label: str, project_name: str) -> str:
    return _compose_title(
        _filename_piece(work_date_label),
        _filename_piece(project_name),
        empty="発注依頼書",
    )


def _compose_title(date: str, project: str, *, empty: str) -> str:
    if date and project:
        return f"{date}：{project}"
    if date:
        return date
    return project or empty


def _display_project_name(project_name: str) -> str:
    text = _plain_piece(project_name)
    if len(text) > 2 and text.startswith("【") and text.endswith("】"):
        inner = text[1:-1].strip()
        if inner:
            return inner
    return text


def _title_markup(
    *,
    notice: str,
    work_date_label: str,
    project_name: str,
    previous_work_date_label: str,
    previous_project_name: str,
) -> str:
    date = _plain_piece(work_date_label)
    project = _display_project_name(project_name)
    line = _compose_title(date, project, empty="")
    if notice == "cancel":
        head = f'<font color="#E61F19">{CANCEL_HEADING}</font>'
    elif notice == "change":
        head = CHANGE_HEADING
    else:
        head = NEW_HEADING
    if not line:
        return head
    shown = escape(line)
    if notice == "change":
        previous_line = _compose_title(
            _plain_piece(previous_work_date_label),
            _display_project_name(previous_project_name),
            empty="",
        )
        if line != previous_line:
            shown = f'<font color="#E61F19">{shown}</font>'
    return f"{head}<br/>{shown}"


def changed_field_captions(
    current: list[tuple[str, str]],
    previous: list[tuple[str, str]],
) -> set[str]:
    before = {caption: _norm_field(text) for caption, text in previous}
    changed: set[str] = set()
    for caption, text in current:
        if before.get(caption) != _norm_field(text):
            changed.add(caption)
    return changed


def _norm_field(value: str) -> str:
    return (value or "").replace("\r\n", "\n").strip()


def _plain_piece(value: str) -> str:
    text = (value or "").replace("~", "～")
    return re.sub(r"\s+", " ", text).strip()


def _filename_piece(value: str) -> str:
    value = _display_project_name(value)
    text = (value or "").translate(str.maketrans({
        "\\": "／",
        "/": "／",
        ":": "：",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
        "\n": " ",
        "\r": " ",
        "\t": " ",
    }))
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:80]


def _reply_note(width: float, styles: dict) -> Table:
    table = Table([[_paragraph(REPLY_NOTE, styles["note"])]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _PAPER),
        ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _field_table(
    fields: list[tuple[str, str]],
    width: float,
    styles: dict,
    changed: set[str] | None = None,
) -> Table:
    changed = changed or set()
    label_width = 32 * mm
    accent_width = 1.8 * mm
    value_width = width - label_width - accent_width
    rows = []
    for caption, text in fields:
        value_style = styles["value_changed"] if caption in changed else styles["value"]
        empty_style = value_style if caption in changed else styles["empty"]
        rows.append([
            "",
            _paragraph(caption, styles["label"]),
            _paragraph(text, value_style, empty_style),
        ])
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
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
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


