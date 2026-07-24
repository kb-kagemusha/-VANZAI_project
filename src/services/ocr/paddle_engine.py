"""PaddleOCR engine wrapper with lazy load and process lock."""
from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any

from src.services.ocr.models import OcrEngineResult, OcrTextLine

if TYPE_CHECKING:
    import numpy as np

_engine = None
_engine_lock = threading.Lock()
_parse_lock = threading.Lock()


def _create_engine():
    from paddleocr import PaddleOCR

    kwargs: dict[str, Any] = {"lang": "japan", "use_gpu": False}
    try:
        return PaddleOCR(use_angle_cls=True, show_log=False, **kwargs)
    except TypeError:
        # PaddleOCR 3.x uses different parameter names / paddlex pipeline.
        return PaddleOCR(**kwargs)


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            if os.getenv("OCR_ENGINE_DISABLED", "").lower() in {"1", "true", "yes"}:
                raise RuntimeError("OCR engine is disabled (OCR_ENGINE_DISABLED)")
            try:
                _engine = _create_engine()
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install with: pip install '.[ocr]'"
                ) from exc
            except RuntimeError as exc:
                raise RuntimeError(
                    "PaddleOCR failed to initialize. "
                    "Use paddleocr<3 (pip install 'paddleocr>=2.7.0,<3.0.0') "
                    "or install paddlex OCR extras."
                ) from exc
    return _engine


def _normalize_raw_result(raw: Any) -> list[list[Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        if raw and isinstance(raw[0], list):
            if raw[0] and isinstance(raw[0][0], (list, tuple)):
                return raw
            return [raw]
    return []


def _lines_from_page(page: list[Any]) -> list[OcrTextLine]:
    lines: list[OcrTextLine] = []
    for item in page:
        if not item:
            continue
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("rec_text") or "").strip()
            confidence = float(item.get("score") or item.get("confidence") or 0.0)
            box = item.get("box") or item.get("dt_polys")
            if text:
                lines.append(OcrTextLine(text=text, confidence=confidence, box=box))
            continue
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        box, text_info = item[0], item[1]
        text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
        confidence = (
            float(text_info[1])
            if isinstance(text_info, (list, tuple)) and len(text_info) > 1
            else 0.0
        )
        lines.append(OcrTextLine(text=str(text).strip(), confidence=confidence, box=box))
    return lines


def run_ocr(image_array: np.ndarray) -> OcrEngineResult:
    """Run OCR on a preprocessed RGB numpy array."""
    with _parse_lock:
        engine = get_engine()
        if hasattr(engine, "ocr"):
            raw = engine.ocr(image_array, cls=True)
        elif hasattr(engine, "predict"):
            raw = engine.predict(image_array)
        else:
            raise RuntimeError("Unsupported PaddleOCR engine API")

    lines: list[OcrTextLine] = []
    for page in _normalize_raw_result(raw):
        lines.extend(_lines_from_page(page))

    full_text = "\n".join(line.text for line in lines if line.text)
    return OcrEngineResult(lines=lines, full_text=full_text)


def run_ocr_from_text(full_text: str) -> OcrEngineResult:
    """Test helper: build engine result from plain text."""
    lines = [OcrTextLine(text=line, confidence=1.0) for line in full_text.splitlines() if line.strip()]
    return OcrEngineResult(lines=lines, full_text=full_text)
