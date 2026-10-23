"""Render only stored invoice header/line snapshots; never resolve live order data."""
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from src.services.pdf_generator import DEFAULT_FONT


def money(value):
    return "¥" + f"{value:,.2f}".rstrip("0").rstrip(".")


def generate_pdf(invoice, lines) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"請求書 {invoice.document_number}", author="VANZAI")
    body = ParagraphStyle("OrderBillingBody", fontName=DEFAULT_FONT, fontSize=10, leading=16, wordWrap="CJK")
    small = ParagraphStyle("OrderBillingSmall", parent=body, fontSize=8, leading=12)
    title = ParagraphStyle("OrderBillingTitle", parent=body, fontSize=23, leading=30, spaceAfter=14)
    right = ParagraphStyle("OrderBillingRight", parent=body, alignment=2)
    def para(value, style=body):
        return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), style)
    story = [para("請求書", title)]
    if invoice.status != "issued":
        story += [para("下書き（未発行）", body), Spacer(1, 3 * mm)]
    issuer = invoice.issuer_snapshot
    issuer_text = "\n".join(filter(None, [issuer["name"], "〒" + issuer["postal_code"] if issuer.get("postal_code") else "",
        issuer.get("address", ""), "登録番号：" + issuer["registration_number"] if issuer.get("registration_number") else ""]))
    parties = Table([[para(invoice.client_snapshot["name"] + " 御中\n" + invoice.client_snapshot.get("address", "")), para(issuer_text, small)]], colWidths=[98 * mm, 76 * mm])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [parties, Spacer(1, 5 * mm)]
    month = f"{invoice.billing_month[:4]}年{int(invoice.billing_month[4:])}月"
    metadata = Table([[para(f"{month}分のご請求"), para(f"請求日：{invoice.billing_date:%Y年%m月%d日}", right)],
        [para(f"請求書番号：{invoice.document_number}", small), para(f"発行日：{invoice.issued_at.astimezone(ZoneInfo('Asia/Tokyo')):%Y年%m月%d日}" if invoice.issued_at else "未発行", right)],
        [para(f"第{invoice.version}版", small), para("")]], colWidths=[112 * mm, 62 * mm])
    metadata.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [metadata, Spacer(1, 6 * mm), para("ご請求金額（税込）　" + money(invoice.total_amount), ParagraphStyle("OrderBillingTotal", parent=body, fontSize=18, leading=26)), Spacer(1, 7 * mm)]
    rows = [[para("依頼内容"), para("数量"), para("税抜金額", right)]]
    for line in lines:
        text = f"{line.description}\n{line.work_date_label}\n依頼書：{line.document_number}"
        if getattr(line, "incentive_amount", None) is not None:
            text += f"\nインセンティブ条件：{line.incentive_note or ''}\n内訳：通常 {money(line.amount - line.incentive_amount)} ＋ インセンティブ {money(line.incentive_amount)}"
        rows.append([para(text, small), para("1件"), para(money(line.amount), right)])
    table = Table(rows, colWidths=[110 * mm, 24 * mm, 40 * mm], repeatRows=1, splitInRow=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#cad1dc")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    totals = Table([[para("税抜小計", right), para(money(invoice.subtotal), right)],
        [para(f"消費税（{invoice.tax_rate * 100:g}%・円未満切捨て）", right), para(money(invoice.tax_amount), right)],
        [para("合計（税込）", right), para(money(invoice.total_amount), right)]], colWidths=[134 * mm, 40 * mm])
    totals.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 6), ("LINEABOVE", (0, -1), (-1, -1), .8, colors.HexColor("#667388"))]))
    story += [table, Spacer(1, 5 * mm), totals]
    if issuer.get("payment_terms"):
        story += [Spacer(1, 6 * mm), para("お支払期限・条件"), para(issuer["payment_terms"], small)]
    if issuer.get("bank_details"):
        story += [Spacer(1, 5 * mm), para("お振込先"), para(issuer["bank_details"], small)]
    def footer(canvas, document):
        canvas.setFont(DEFAULT_FONT, 8)
        canvas.setFillColor(colors.HexColor("#667388"))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"VANZAI / {document.page}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
