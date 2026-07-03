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
    """Header band: store name, registration, terminal short id."""
    return _preprocess_settlement_band(image_bytes, y0=0.06, y1=0.26, scale=4.0)


def preprocess_settlement_terminal_band(image_bytes: bytes) -> np.ndarray:
    """Terminal UUID band: often missed on a single full-image pass."""
    return _preprocess_settlement_band(image_bytes, y0=0.18, y1=0.40, scale=4.0)


def run_settlement_ocr(image_bytes: bytes) -> OcrEngineResult:
    """Run focused band OCR first, then default passes, and merge line texts."""
    return merge_ocr_results(
        run_ocr(preprocess_settlement_header_band(image_bytes)),
        run_ocr(preprocess_settlement_terminal_band(image_bytes)),
        run_ocr(preprocess_for_ocr(image_bytes)),
        run_ocr(preprocess_upscaled_for_ocr(image_bytes, scale=2.0, max_width=2800)),
    )
