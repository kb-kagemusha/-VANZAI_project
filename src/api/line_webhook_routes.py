"""公式LINEのWebhookと、送付PDFの一時URL。ログインは不要。署名とトークンで制限する。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.services.line_messaging import line_settings, verify_line_signature
from src.services.line_order import LineOrderService
from src.services.order_request_pdf import attachment_content_disposition
from src.services.order_request_service import OrderRequestError

router = APIRouter(prefix="/api/line", tags=["LINE"])


@router.post("/webhook")
async def line_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    settings = line_settings()
    if not settings.channel_secret:
        raise HTTPException(status_code=503, detail="LINEのチャネルシークレットが未設定です")
    signature = request.headers.get("x-line-signature", "")
    if not verify_line_signature(body, signature, settings.channel_secret):
        raise HTTPException(status_code=400, detail="署名が正しくありません")
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail="Webhookの本文を読めません") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhookの本文を読めません")
    try:
        LineOrderService(db).handle_webhook(payload)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"ok": True}


@router.get("/order-request-files/{token}")
def download_shared_order_request_pdf(token: str, db: Session = Depends(get_db)):
    if "/" in token or len(token) > 80:
        raise HTTPException(status_code=404, detail="PDFのリンクは無効です")
    try:
        service = LineOrderService(db)
        content = service.read_shared_pdf(token)
        filename = service.shared_pdf_filename(token)
    except OrderRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": attachment_content_disposition(filename),
            "Cache-Control": "no-store",
        },
    )
