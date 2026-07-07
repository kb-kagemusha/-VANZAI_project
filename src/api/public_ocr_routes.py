"""Public OCR upload routes (no login required)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import OcrPublicUploadAccessResponse, OcrPublicUploadResponse
from src.services.ocr.parsers.paygate_payment import PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE
from src.services.ocr.upload_validation import HEIC_REJECTION_MESSAGE
from src.services.ocr_upload_link_service import OcrUploadLinkService

router = APIRouter(tags=["OCR Public Upload"])

_REFERRER_POLICY = {"Referrer-Policy": "no-referrer"}


def _json_response(payload, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=payload, status_code=status_code, headers=_REFERRER_POLICY)


def _permission_error_to_http(exc: PermissionError) -> HTTPException:
    code = str(exc)
    if code in {"link_revoked", "link_expired"}:
        return HTTPException(status_code=410, detail="このアップロードリンクは利用できません")
    if code == "rate_limit":
        return HTTPException(status_code=429, detail="アップロード回数の上限に達しました。しばらく待ってから再度お試しください")
    if code == "upload_limit":
        return HTTPException(status_code=429, detail="このリンクのアップロード上限に達しました")
    if code in {"session_invalid", "session_revoked", "session_expired"}:
        return HTTPException(status_code=401, detail="セッションが無効です。リンクから再度アクセスしてください")
    return HTTPException(status_code=403, detail="アクセスできません")


@router.get("/public/ocr-upload")
def access_public_ocr_upload(
    token: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
):
    service = OcrUploadLinkService(db)
    link = service.get_link_by_token(token)
    if link is None:
        raise HTTPException(status_code=404, detail="アップロードリンクが見つかりません")
    try:
        service._ensure_link_usable(link)
    except PermissionError as exc:
        raise _permission_error_to_http(exc) from exc

    _, session_token = service.create_session(link)
    db.commit()
    db.refresh(link)
    session_row = service.get_session_by_token(session_token)
    return _json_response(
        OcrPublicUploadAccessResponse(
            link_id=link.id,
            label=link.label,
            expires_at=link.expires_at,
            public_memo=link.public_memo,
            default_source_type=link.default_source_type,
            session_token=session_token,
            session_expires_at=session_row.expires_at if session_row else link.expires_at,
        ).model_dump(mode="json")
    )


@router.post("/public/ocr-upload/images", status_code=202)
async def upload_public_ocr_image(
    request: Request,
    source_type: str = Form(...),
    file: UploadFile = File(...),
    public_uploader_name: str | None = Form(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="セッションが無効です。リンクから再度アクセスしてください")
    session_token = authorization.split(" ", 1)[1].strip()
    service = OcrUploadLinkService(db)
    try:
        _, link = service.resolve_session(session_token)
    except PermissionError as exc:
        raise _permission_error_to_http(exc) from exc

    file_bytes = await file.read()
    normalized_uploader_name = (public_uploader_name or "").strip()
    if not normalized_uploader_name:
        raise HTTPException(status_code=400, detail="お名前は必須です")
    try:
        result = service.handle_public_upload(
            link=link,
            source_type=source_type,
            file_bytes=file_bytes,
            file_name=file.filename,
            public_uploader_name=normalized_uploader_name,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
    except PermissionError as exc:
        db.rollback()
        raise _permission_error_to_http(exc) from exc
    except ValueError as exc:
        db.rollback()
        code = str(exc)
        if code == "invalid_paygate_image":
            raise HTTPException(
                status_code=422,
                detail=PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE,
            ) from exc
        if code == "heic":
            raise HTTPException(status_code=415, detail=HEIC_REJECTION_MESSAGE) from exc
        if code == "too_large":
            raise HTTPException(status_code=413, detail="ファイルサイズが大きすぎます") from exc
        if code in {"unsupported_type", "invalid_image", "invalid_file"}:
            raise HTTPException(status_code=415, detail="対応していない画像形式です") from exc
        if code == "invalid_source_type":
            raise HTTPException(status_code=422, detail="画像種別が不正です") from exc
        if code == "uploader_name_required":
            raise HTTPException(status_code=400, detail="お名前は必須です") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    return _json_response(OcrPublicUploadResponse(**result).model_dump(mode="json"), status_code=202)
