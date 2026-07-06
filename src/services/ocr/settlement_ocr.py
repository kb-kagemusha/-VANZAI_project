"""Multi-pass OCR tuned for Paygate settlement (精算) receipts."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from src.services.ocr.image_preprocess import preprocess_for_ocr, preprocess_upscaled_for_ocr
from src.services.ocr.merge_results import merge_ocr_results
from src.services.ocr.models import OcrEngineResult
from src.services.ocr.paddle_engine import run_ocr


def _preprocess_settlement_band(
    image_bytes: bytes,
    *,
    y0: float,
    y1: float,
    scale: float = 4.0,
    max_width: int = 3200,
) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    band = image.crop((0, int(height * y0), width, int(height * y1)))
    gray = ImageOps.grayscale(band)
    gray = ImageOps.autocontrast(gray, cutoff=2)
    gray = ImageEnhance.Contrast(gray).enhance(2.2)
    gray = gray.filter(ImageFilter.SHARPEN)
    target_width = min(max(int(band.width * scale), band.width), max_width)
    ratio = target_width / band.width
    target_height = max(1, int(band.height * ratio))
    upscaled = gray.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return np.array(upscaled.convert("RGB"))


def preprocess_settlement_header_band(image_bytes: bytes) -> np.ndarray:
    """Header band: 端末識別番号・登録番号（画像上端ギリギリの印字向け）。"""
    return _preprocess_settlement_band(image_bytes, y0=0.0, y1=0.22, scale=4.0)


def preprocess_settlement_id_line_band(image_bytes: bytes) -> np.ndarray:
    """端末識別番号〜精算タイトル帯（感熱紙の薄い上段向け）。"""
    return _preprocess_settlement_band(image_bytes, y0=0.08, y1=0.30, scale=5.0, max_width=3600)


def preprocess_settlement_datetime_band(image_bytes: bytes) -> np.ndarray:
    """精算タイトル直下の日時行（スラッシュ・コロン欠落しやすい帯）向け。"""
    return _preprocess_settlement_band(image_bytes, y0=0.14, y1=0.34, scale=5.5, max_width=3600)


def preprocess_settlement_terminal_band(image_bytes: bytes) -> np.ndarray:
    """Terminal UUID band: often missed on a single full-image pass."""
    return _preprocess_settlement_band(image_bytes, y0=0.18, y1=0.40, scale=4.0)


def preprocess_settlement_uuid_wide_band(image_bytes: bytes) -> np.ndarray:
    """端末番号 UUID が折り返す帯域を広めに取得。"""
    return _preprocess_settlement_band(image_bytes, y0=0.16, y1=0.48, scale=4.5, max_width=3600)


def preprocess_settlement_uuid_mid_band(image_bytes: bytes) -> np.ndarray:
    """端末番号の折り返し中腹（a0c1-49be-af4c 付近）向けの狭い高解像度帯。"""
    return _preprocess_settlement_band(image_bytes, y0=0.20, y1=0.36, scale=6.0, max_width=3800)


def run_settlement_ocr(image_bytes: bytes) -> OcrEngineResult:
    """Run focused header/terminal band OCR first, then default passes, and merge."""
    return merge_ocr_results(
        run_ocr(preprocess_settlement_header_band(image_bytes)),
        run_ocr(preprocess_settlement_id_line_band(image_bytes)),
        run_ocr(preprocess_settlement_datetime_band(image_bytes)),
        run_ocr(preprocess_settlement_terminal_band(image_bytes)),
        run_ocr(preprocess_settlement_uuid_mid_band(image_bytes)),
        run_ocr(preprocess_settlement_uuid_wide_band(image_bytes)),
        run_ocr(preprocess_for_ocr(image_bytes)),
        run_ocr(preprocess_upscaled_for_ocr(image_bytes, scale=2.0, max_width=2800)),
    )
