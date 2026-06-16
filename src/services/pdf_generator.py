"""
PDF生成サービス

請求書と支払明細のPDF生成を担当
- 和文フォント対応
- レイアウト・スタイル統一
- 版管理対応（再発行時にversion表示）

仕様参照: DESIGN_SPEC_v0.3.md「請求書・支払明細生成」
"""
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Any
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..models.transaction import Invoice, InvoiceLine, Payout, PayoutLine
from ..models.enums import LineType


def _safe_amount(value: Decimal | None) -> str:
    return f"¥{value:,.0f}" if value is not None else "-"


# 日本語フォント設定（システムフォントを使用）
# Windows環境を想定
try:
    font_path = "C:/Windows/Fonts/msgothic.ttc"  # MSゴシック
    pdfmetrics.registerFont(TTFont("MSGothic", font_path))
    DEFAULT_FONT = "MSGothic"
except Exception:
    # フォントが見つからない場合はHelveticaを使用
    DEFAULT_FONT = "Helvetica"


class PDFGenerator:
    """PDF生成サービス"""

    def __init__(self, output_dir: Path | None = None):
        """
        Args:
            output_dir: PDF出力ディレクトリ（Noneの場合はメモリ上に生成）
        """
        self.output_dir = output_dir
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

    def generate_invoice_pdf(
        self, invoice: Invoice, lines: list[InvoiceLine]
    ) -> bytes | str:
        """
        請求書PDFを生成

        Args:
            invoice: 請求書オブジェクト
            lines: 請求明細行リスト

        Returns:
            output_dirが指定されている場合はファイルパス、未指定の場合はPDFバイナリ
        """
        if self.output_dir:
            filename = f"invoice_{invoice.id}_v{invoice.version}.pdf"
            filepath = self.output_dir / filename
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        else:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)

        # スタイル設定
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontName=DEFAULT_FONT,
            fontSize=16,
            alignment=TA_CENTER,
        )
        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=10,
        )
        right_style = ParagraphStyle(
            "RightStyle",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=10,
            alignment=TA_RIGHT,
        )

        # ドキュメント要素を構築
        story = []

        # タイトル
        document_title = self._format_invoice_document_type(getattr(invoice, "document_type", "invoice"))
        if invoice.version > 1:
            title = Paragraph(
                f"{document_title}（再発行版 {invoice.version}）", title_style
            )
        else:
            title = Paragraph(document_title, title_style)
        story.append(title)
        story.append(Spacer(1, 12 * mm))

        addressee_lines = []
        if getattr(invoice, "addressee_company_name", None):
            addressee_lines.append(str(invoice.addressee_company_name))
        if getattr(invoice, "addressee_name", None):
            addressee_lines.append(f"{invoice.addressee_name} 様")
        addressee_text = "<br/>".join(addressee_lines) if addressee_lines else (invoice.client.name if invoice.client else "-")
        story.append(Paragraph(addressee_text, normal_style))
        if getattr(invoice, "addressee_address", None):
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(str(invoice.addressee_address).replace("\n", "<br/>"), normal_style))
        story.append(Spacer(1, 6 * mm))

        if getattr(invoice, "invoice_subject", None):
            story.append(Paragraph(f"<b>件名:</b> {invoice.invoice_subject}", normal_style))
            story.append(Spacer(1, 4 * mm))

        # ヘッダー情報
        header_data = [
            ["請求書番号", invoice.id],
            ["請求先", invoice.client.name if invoice.client else "-"],
            ["請求期間", f"{invoice.period_key}"],
            ["帳票種別", document_title],
            ["請求日", invoice.billing_date.strftime("%Y年%m月%d日") if invoice.billing_date else "-"],
            ["発行日", invoice.issued_at.strftime("%Y年%m月%d日") if invoice.issued_at else "-"],
            ["請求金額（税込）", f"¥{invoice.total_amount:,.0f}"],
        ]

        header_table = Table(header_data, colWidths=[40 * mm, 120 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), DEFAULT_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 10 * mm))

        # 明細テーブル
        detail_data = [["種別", "説明", "数量", "単価", "金額"]]

        for line in lines:
            line_type = self._format_line_type(line.line_type)
            quantity = f"{line.quantity_snapshot:,.2f}" if line.quantity_snapshot is not None else "-"
            unit_price = _safe_amount(line.unit_price_snapshot)
            amount = _safe_amount(line.line_amount)

            detail_data.append(
                [line_type, line.description, quantity, unit_price, amount]
            )

        # 合計行
        detail_data.append(["", "", "", "小計", _safe_amount(invoice.subtotal)])
        detail_data.append(
            ["", "", "", f"消費税", _safe_amount(invoice.tax_amount)]
        )
        detail_data.append(
            ["", "", "", "合計", _safe_amount(invoice.total_amount)]
        )

        detail_table = Table(
            detail_data,
            colWidths=[25 * mm, 75 * mm, 20 * mm, 25 * mm, 30 * mm],
        )
        detail_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), DEFAULT_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (2, 0), (4, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -2), 0.5, colors.black),
                    ("LINEABOVE", (3, -3), (-1, -3), 1, colors.black),
                    ("LINEABOVE", (3, -1), (-1, -1), 2, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(detail_table)
        story.append(Spacer(1, 10 * mm))

        # 備考
        if hasattr(invoice, 'notes') and invoice.notes:
            memo_text = Paragraph(f"<b>備考:</b> {invoice.notes}", normal_style)
            story.append(memo_text)

        # PDF生成
        doc.build(story)

        if self.output_dir:
            return str(filepath)
        else:
            return buffer.getvalue()

    def generate_payout_pdf(
        self, payout: Payout, lines: list[PayoutLine]
    ) -> bytes | str:
        """
        支払明細PDFを生成

        Args:
            payout: 支払明細オブジェクト
            lines: 支払明細行リスト

        Returns:
            output_dirが指定されている場合はファイルパス、未指定の場合はPDFバイナリ
        """
        if self.output_dir:
            filename = f"payout_{payout.id}_v{payout.version}.pdf"
            filepath = self.output_dir / filename
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        else:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)

        # スタイル設定
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontName=DEFAULT_FONT,
            fontSize=16,
            alignment=TA_CENTER,
        )
        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontName=DEFAULT_FONT,
            fontSize=10,
        )

        # ドキュメント要素を構築
        story = []

        # タイトル
        if payout.version > 1:
            title = Paragraph(
                f"支払明細書（訂正版 {payout.version}）", title_style
            )
        else:
            title = Paragraph("支払明細書", title_style)
        story.append(title)
        story.append(Spacer(1, 12 * mm))

        # ヘッダー情報
        payee_name = payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else "-")
        header_data = [
            ["明細番号", payout.id],
            ["支払先", payee_name],
            ["対象期間", f"{payout.period_key}"],
            ["確定日", payout.approved_at.strftime("%Y年%m月%d日") if payout.approved_at else "-"],
            ["支払金額", _safe_amount(payout.total_amount)],
        ]

        header_table = Table(header_data, colWidths=[40 * mm, 120 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), DEFAULT_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 10 * mm))

        # 明細テーブル
        detail_data = [["種別", "説明", "数量", "単価", "金額"]]

        for line in lines:
            line_type = self._format_line_type(line.line_type)
            quantity = f"{line.quantity_snapshot:,.2f}" if line.quantity_snapshot is not None else "-"
            unit_price = _safe_amount(line.unit_price_snapshot)
            amount = _safe_amount(line.line_amount)

            detail_data.append(
                [line_type, line.description, quantity, unit_price, amount]
            )

        # 合計行
        detail_data.append(["", "", "", "合計", _safe_amount(payout.total_amount)])

        detail_table = Table(
            detail_data,
            colWidths=[25 * mm, 75 * mm, 20 * mm, 25 * mm, 30 * mm],
        )
        detail_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), DEFAULT_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (2, 0), (4, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -2), 0.5, colors.black),
                    ("LINEABOVE", (3, -1), (-1, -1), 2, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(detail_table)
        story.append(Spacer(1, 10 * mm))

        # 備考
        if hasattr(payout, 'notes') and payout.notes:
            memo_text = Paragraph(f"<b>備考:</b> {payout.notes}", normal_style)
            story.append(memo_text)

        # PDF生成
        doc.build(story)

        if self.output_dir:
            return str(filepath)
        else:
            return buffer.getvalue()

    def _format_line_type(self, line_type: LineType) -> str:
        """明細行種別を日本語に変換"""
        mapping = {
            LineType.WORK: "稼働",
            LineType.EXPENSE: "経費",
            LineType.INCENTIVE: "インセンティブ",
            "actual": "稼働",
            "work": "稼働",
            "expense": "経費",
            "incentive": "インセンティブ",
            "office_fee": "固定事務局費",
        }
        return mapping.get(line_type, str(line_type))

    def _format_invoice_document_type(self, document_type: str) -> str:
        mapping = {
            "invoice": "請 求 書",
            "estimate": "見 積 書",
        }
        return mapping.get(document_type, "請 求 書")
