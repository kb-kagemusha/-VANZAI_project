"""Image preprocessing before OCR."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageOps


def load_image_bytes(image_bytes: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    return np.array(image)


def preprocess_blue_amount_channel(image_bytes: bytes, *, max_width: int = 2000) -> np.ndarray:
    """Isolate Paygate blue amount text as black-on-white for a focused OCR pass."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    if image.width > max_width:
        new_height = max(1, int(image.height * max_width / image.width))
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    rgb = np.array(image, dtype=np.int16)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    blue_text = (blue >= 90) & (blue >= red + 20) & (blue >= green + 10) & ((red + green + blue) < 760)

    isolated = np.full((image.height, image.width, 3), 255, dtype=np.uint8)
    isolated[blue_text] = (0, 0, 0)
    return np.array(ImageOps.autocontrast(Image.fromarray(isolated)).convert("RGB"))


def preprocess_for_ocr(image_bytes: bytes, *, max_width: int = 2000) -> np.ndarray:
    """Resize and enhance image for OCR using Pillow only (avoids OpenCV worker conflicts)."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    if image.width > max_width:
        new_height = max(1, int(image.height * max_width / image.width))
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    rgb = np.array(image, dtype=np.int16)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    # Paygate amount text is blue on a light background; strengthen it before grayscale OCR.
    blue_text = (blue >= 100) & (blue >= red + 25) & (blue >= green + 15) & ((red + green + blue) < 720)

    gray = np.array(ImageOps.grayscale(image), dtype=np.int16)
    enhanced = gray.copy()
    enhanced[blue_text] = np.clip(gray[blue_text] * 0.25, 0, 255)
    enhanced[~blue_text] = np.clip(gray[~blue_text] * 1.05, 0, 255)
    enhanced_image = ImageOps.autocontrast(Image.fromarray(enhanced.astype(np.uint8))).convert("RGB")
    return np.array(enhanced_image)


def preprocess_upscaled_for_ocr(
    image_bytes: bytes,
    *,
    scale: float = 2.0,
    max_width: int = 2400,
) -> np.ndarray:
    """Upscale small phone screenshots before OCR to improve character separation."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")

    target_width = min(max(image.width, int(image.width * scale)), max_width)
    if target_width > image.width:
        new_height = max(1, int(image.height * target_width / image.width))
        image = image.resize((target_width, new_height), Image.Resampling.LANCZOS)

    gray = np.array(ImageOps.grayscale(image), dtype=np.int16)
    enhanced = ImageOps.autocontrast(Image.fromarray(gray.astype(np.uint8))).convert("RGB")
    return np.array(enhanced)
