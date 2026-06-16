"""PaddleOCR engine wrapper with lazy load and process lock."""
from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

from src.services.ocr.models import OcrEngineResult, OcrTextLine

if TYPE_CHECKING:
    import numpy as np

_engine = None
_engine_lock = threading.Lock()
_parse_lock = threading.Lock()


def _create_engine():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        use_angle_cls=True,
        lang="japan",
        show_log=False,
        use_gpu=False,
    )


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
                    "PaddleOCR is not installed. Install with: pip install paddlepaddle paddleocr"
                ) from exc
    return _engine


def run_ocr(image_array: np.ndarray) -> OcrEngineResult:
    """Run OCR on a preprocessed RGB numpy array."""
    with _parse_lock:
        engine = get_engine()
        raw = engine.ocr(image_array, cls=True)

    lines: list[OcrTextLine] = []
    if not raw:
        return OcrEngineResult(lines=[], full_text="")

    for page in raw:
        if not page:
            continue
        for item in page:
            if not item or len(item) < 2:
                continue
            box, text_info = item[0], item[1]
            text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
            confidence = float(text_info[1]) if isinstance(text_info, (list, tuple)) and len(text_info) > 1 else 0.0
            lines.append(OcrTextLine(text=text.strip(), confidence=confidence, box=box))

    full_text = "\n".join(line.text for line in lines if line.text)
    return OcrEngineResult(lines=lines, full_text=full_text)


def run_ocr_from_text(full_text: str) -> OcrEngineResult:
    """Test helper: build engine result from plain text."""
    lines = [OcrTextLine(text=line, confidence=1.0) for line in full_text.splitlines() if line.strip()]
    return OcrEngineResult(lines=lines, full_text=full_text)
