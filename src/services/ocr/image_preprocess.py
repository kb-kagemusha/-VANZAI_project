"""Image preprocessing before OCR."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image


def load_image_bytes(image_bytes: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    return np.array(image)


def preprocess_for_ocr(image_bytes: bytes, *, max_width: int = 2000) -> np.ndarray:
    """Resize and enhance image for OCR."""
    try:
        import cv2
    except ImportError:
        return load_image_bytes(image_bytes)

    rgb = load_image_bytes(image_bytes)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    if width > max_width:
        scale = max_width / width
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
