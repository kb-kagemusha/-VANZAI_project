"""
PDF生成サービスの統合テスト（簡略版）
"""
import pytest
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
import tempfile
import shutil

from src.services.pdf_generator import PDFGenerator
from src.models.transaction import Invoice, InvoiceLine, Payout, PayoutLine, Project
from src.models.master import Client, Worker, Site
from src.models.enums import LineType, InvoiceStatus, PayoutStatus


def test_generate_invoice_pdf():
    """請求書PDFをメモリ上に生成"""
    # Arrange
    generator = PDFGenerator()

    invoice = Invoice()
    invoice.id = "01INV002"
    invoice.client_id = "01CLIENT001"
    invoice.period_key = "202401"
    invoice.subtotal = Decimal("50000")
    invoice.tax_amount = Decimal("5000")
    invoice.total_amount = Decimal("55000")
    invoice.status = InvoiceStatus.PREPARING.value
    invoice.version = 1
    invoice.issued_at = datetime(2024, 2, 1, tzinfo=timezone.utc)

    client = Client()
    client.id = "01CLIENT001"
    client.name = "テスト株式会社"
    invoice.client = client

    line = InvoiceLine()
    line.id = "01LINE002"
    line.invoice_id = invoice.id
    line.line_type = LineType.WORK.value
    line.project_id = "01PRJ001"
    line.worker_id = "01WORKER001"
    line.line_number = 1
    line.description = "稼働"
    line.unit_price_snapshot = Decimal("5000")
    line.quantity_snapshot = Decimal("80")
    line.unit_type = "hours"
    line.line_amount = Decimal("400000")

    project = Project()
    project.id = "01PRJ001"
    project.name = "テストプロジェクト"
    line.project = project

    worker = Worker()
    worker.id = "01WORKER001"
    worker.name = "山田太郎"
    line.worker = worker

    # Act
    result = generator.generate_invoice_pdf(invoice, [line])

    # Assert
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"%PDF"  # PDFファイルヘッダー


def test_generate_payout_pdf():
    """支払明細PDFをメモリ上に生成"""
    # Arrange
    generator = PDFGenerator()

    payout = Payout()
    payout.id = "01PAY002"
    payout.worker_id = "01WORKER001"
    payout.period_key = "202401"
    payout.subtotal = Decimal("150000")
    payout.tax_amount = Decimal("15000")
    payout.total_amount = Decimal("165000")
    payout.status = PayoutStatus.PREPARING.value
    payout.version = 1
    payout.confirmed_at = datetime(2024, 2, 5, tzinfo=timezone.utc)

    worker = Worker()
    worker.id = "01WORKER001"
    worker.name = "山田太郎"
    payout.worker = worker

    line = PayoutLine()
    line.id = "01PAYLINE002"
    line.payout_id = payout.id
    line.line_type = LineType.WORK.value
    line.project_id = "01PRJ001"
    line.site_id = "01SITE001"
    line.line_number = 1
    line.description = "稼働"
    line.unit_price_snapshot = Decimal("3000")
    line.quantity_snapshot = Decimal("80")
    line.unit_type = "hours"
    line.line_amount = Decimal("240000")

    project = Project()
    project.id = "01PRJ001"
    project.name = "テストプロジェクト"
    line.project = project

    site = Site()
    site.id = "01SITE001"
    site.name = "新宿オフィス"
    line.site = site

    # Act
    result = generator.generate_payout_pdf(payout, [line])

    # Assert
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"%PDF"


def test_generate_invoice_pdf_to_file():
    """請求書PDFをファイルに生成"""
    # Arrange
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        generator = PDFGenerator(output_dir=tmp_dir)

        invoice = Invoice()
        invoice.id = "01INV001"
        invoice.client_id = "01CLIENT001"
        invoice.period_key = "202401"
        invoice.subtotal = Decimal("100000")
        invoice.tax_amount = Decimal("10000")
        invoice.total_amount = Decimal("110000")
        invoice.status = InvoiceStatus.PREPARING.value
        invoice.version = 1
        invoice.issued_at = datetime(2024, 2, 1, tzinfo=timezone.utc)

        client = Client()
        client.id = "01CLIENT001"
        client.name = "テスト株式会社"
        invoice.client = client

        line = InvoiceLine()
        line.id = "01LINE001"
        line.invoice_id = invoice.id
        line.line_type = LineType.WORK.value
        line.project_id = "01PRJ001"
        line.worker_id = "01WORKER001"
        line.line_number = 1
        line.description = "稼働"
        line.unit_price_snapshot = Decimal("5000")
        line.quantity_snapshot = Decimal("160")
        line.unit_type = "hours"
        line.line_amount = Decimal("800000")

        project = Project()
        project.id = "01PRJ001"
        project.name = "テストプロジェクト"
        line.project = project

        worker = Worker()
        worker.id = "01WORKER001"
        worker.name = "山田太郎"
        line.worker = worker

        # Act
        result = generator.generate_invoice_pdf(invoice, [line])

        # Assert
        assert isinstance(result, str)
        assert Path(result).exists()
        assert Path(result).suffix == ".pdf"
        assert "invoice_01INV001_v1.pdf" in result
    finally:
        shutil.rmtree(tmp_dir)
