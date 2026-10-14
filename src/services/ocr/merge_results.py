"""Merge multiple OCR passes into one engine result."""
from __future__ import annotations

from src.services.ocr.models import OcrEngineResult, OcrTextLine


def _line_center(line: OcrTextLine) -> tuple[float, float]:
    if not line.box:
        return 0.0, 0.0
    xs = [point[0] for point in line.box]
    ys = [point[1] for point in line.box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def merge_ocr_results(*results: OcrEngineResult) -> OcrEngineResult:
    merged: list[OcrTextLine] = []
    seen: set[tuple[str, int, int]] = set()
    for result in results:
        for line in result.lines:
            text = line.text.strip()
            if not text:
                continue
            x, y = _line_center(line)
            key = (text, round(x / 10), round(y / 10))
            if key in seen:
                continue
            seen.add(key)
            merged.append(line)
    full_text = "\n".join(line.text for line in merged)
    return OcrEngineResult(lines=merged, full_text=full_text)
