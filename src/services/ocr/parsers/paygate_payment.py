"""Normalize and extract Paygate screenshot payment method (決済方法)."""
from __future__ import annotations

import re

from src.services.ocr.models import OcrTextLine
from src.services.ocr.parsers.paygate_datetime import normalize_paygate_ocr_text

ALLOWED_PAYGATE_PAYMENT_METHODS = frozenset({"現金", "QRコード", "クレジット"})

PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE = (
    "正しいPaygateの画像ではありません。"
    "決済方法の記載があるスクリーンショットの画像をアップロードし直してください。"
)

_PAYMENT_METHOD_LABEL_RE = re.compile(r"決\s*済\s*方\s*法")
_PAYMENT_METHOD_LABEL_OCR_RE = re.compile(r"決[済消湾]\s*方\s*法")
_PAYMENT_LABEL_FLEX_RE = re.compile(r"決\s*[済消湾]\s*方\s*法")
_PAYMENT_LABEL_SPLIT_RE = re.compile(r"^(.*?)(決\s*[済消湾]\s*方\s*法)(.*)$", re.DOTALL)
_DATETIME_LINE_RE = re.compile(r"\d{4}[/,，.\-]\d{2}[/,，.\-]\d{2}[\s\n]+\d{2}:\d{2}:\d{2}")
_NEXT_FIELD_RE = re.compile(r"^(?:取引番号|レシート番号|\d{4}/\d{2}/\d{2})")
_QR_FRAGMENT_RE = re.compile(
    r"(?:QR|ＱＲ|[O0Ｏ０][RＲ]|Q\s*R)[\.:\s\u3000]*"
    r"(?:コード|コ\s*ー\s*ド|コ一ド|コ-ド)",
    re.IGNORECASE,
)

_PAYMENT_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^現金$"), "現金"),
    (re.compile(r"^qr[\s\u3000]*(?:コード|コ\s*ー\s*ド|コ一ド|コ-ド)$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^qr$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^qrcode$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^[o0Ｏ０][rRＲ][\s\u3000]*(?:コード|コ\s*ー\s*ド|コ一ド|コ-ド)$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^ＱＲ[\s\u3000]*(?:コード|コ\s*ー\s*ド|コ一ド|コ-ド)$"), "QRコード"),
    (re.compile(r"^クレジット(?:カード)?$"), "クレジット"),
    (re.compile(r"^クレヂット(?:カード)?$"), "クレジット"),
)


def paygate_screenshot_has_payment_method_label(text: str) -> bool:
    """Return True when OCR text includes the Paygate screenshot 決済方法 label."""
    if not text or not text.strip():
        return False
    normalized = normalize_paygate_ocr_text(text)
    compact = re.sub(r"\s+", "", normalized)
    if "決済方法" in compact:
        return True
    if _PAYMENT_METHOD_LABEL_RE.search(normalized):
        return True
    return bool(_PAYMENT_METHOD_LABEL_OCR_RE.search(normalized))


def normalize_paygate_payment_method(value: str | None) -> str | None:
    """Return canonical payment method or None if missing/invalid."""
    if not value:
        return None
    cleaned = value.strip().replace("　", " ")
    if cleaned in ALLOWED_PAYGATE_PAYMENT_METHODS:
        return cleaned
    lowered = cleaned.lower()
    for pattern, canonical in _PAYMENT_ALIASES:
        if pattern.match(cleaned) or pattern.match(lowered):
            return canonical
    compact = re.sub(r"\s+", "", cleaned)
    if compact in ALLOWED_PAYGATE_PAYMENT_METHODS:
        return compact
    for pattern, canonical in _PAYMENT_ALIASES:
        if pattern.match(compact):
            return canonical
    if _QR_FRAGMENT_RE.search(cleaned) or _QR_FRAGMENT_RE.search(compact):
        return "QRコード"
    return None


def _line_x_center(line: OcrTextLine) -> float:
    if not line.box:
        return 0.0
    xs = [point[0] for point in line.box]
    return sum(xs) / len(xs)


def _line_y_center(line: OcrTextLine) -> float:
    if not line.box:
        return 0.0
    ys = [point[1] for point in line.box]
    return sum(ys) / len(ys)


def _lines_in_block(lines: list[OcrTextLine], block: str) -> list[OcrTextLine]:
    return [line for line in lines if line.text.strip() and line.text.strip() in block]


def _is_payment_label_line(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return bool(
        _PAYMENT_LABEL_FLEX_RE.search(text)
        or _PAYMENT_METHOD_LABEL_RE.search(text)
        or "決済方法" in compact
    )


def _block_has_payment_label(block: str) -> bool:
    return paygate_screenshot_has_payment_method_label(block)


def _normalize_from_raw_text(raw: str) -> str | None:
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip().replace("　", " ")
    normalized = normalize_paygate_payment_method(cleaned)
    if normalized:
        return normalized
    compact = re.sub(r"\s+", "", cleaned)
    return normalize_paygate_payment_method(compact)


def _strip_next_field_prefix(raw: str) -> str:
    return re.split(r"[\n]|(?=取引番号|レシート番号|\d{4}/\d{2}/\d{2})", raw)[0].strip()


def _payment_from_inline_text(block: str) -> str | None:
    match = re.search(
        r"決\s*[済消湾]\s*方\s*法[\s\n]+(.+?)(?:\n(?:取引番号|レシート番号|\d{4}/\d{2}/\d{2})|\Z)",
        block,
        re.DOTALL,
    )
    if not match:
        return None
    raw = _strip_next_field_prefix(match.group(1))
    if not raw:
        return None
    return _normalize_from_raw_text(raw)


def _payment_from_line_order(block_lines: list[str]) -> str | None:
    for index, line in enumerate(block_lines):
        if not _is_payment_label_line(line):
            continue

        split = _PAYMENT_LABEL_SPLIT_RE.match(line)
        inline_value = split.group(3).strip() if split else ""
        if inline_value:
            normalized = _normalize_from_raw_text(inline_value)
            if normalized:
                return normalized

        collected: list[str] = []
        for candidate in block_lines[index + 1 : index + 4]:
            if not candidate.strip() or _NEXT_FIELD_RE.match(candidate.strip()):
                break
            collected.append(candidate.strip())
            combined = " ".join([inline_value, *collected]).strip() if inline_value else " ".join(collected)
            normalized = _normalize_from_raw_text(combined)
            if normalized:
                return normalized
    return None


def _payment_from_block_scan(block: str) -> str | None:
    if not _block_has_payment_label(block):
        return None
    labels = list(_PAYMENT_LABEL_FLEX_RE.finditer(block))
    if len(labels) != 1:
        return None

    for method in ("現金", "クレジット"):
        if re.search(rf"(?<![\w]){method}(?![\w])", block):
            return method
    if _QR_FRAGMENT_RE.search(block) or "QRコード" in block.replace(" ", ""):
        return "QRコード"
    return None


def _payment_from_spatial_lines(lines: list[OcrTextLine]) -> str | None:
    label_lines = [line for line in lines if _is_payment_label_line(line.text)]
    for label_line in label_lines:
        ref_y = _line_y_center(label_line)
        ref_x = _line_x_center(label_line)

        split = _PAYMENT_LABEL_SPLIT_RE.match(label_line.text.strip())
        if split and split.group(3).strip():
            normalized = _normalize_from_raw_text(split.group(3))
            if normalized:
                return normalized

        same_row = [
            line
            for line in lines
            if line is not label_line and abs(_line_y_center(line) - ref_y) <= 28
        ]
        if same_row:
            row_text = " ".join(line.text.strip() for line in sorted(same_row, key=_line_x_center))
            row_text = _PAYMENT_LABEL_FLEX_RE.sub("", row_text).strip()
            normalized = _normalize_from_raw_text(row_text)
            if normalized:
                return normalized

        right_side = [
            line
            for line in lines
            if line is not label_line
            and abs(_line_y_center(line) - ref_y) <= 28
            and _line_x_center(line) > ref_x + 40
        ]
        for line in sorted(right_side, key=_line_x_center, reverse=True):
            normalized = _normalize_from_raw_text(line.text)
            if normalized:
                return normalized

        below_right = [
            line
            for line in lines
            if line is not label_line
            and 5 <= _line_y_center(line) - ref_y <= 45
            and _line_x_center(line) > ref_x + 30
        ]
        for line in sorted(below_right, key=lambda item: (_line_y_center(item), -_line_x_center(item))):
            normalized = _normalize_from_raw_text(line.text)
            if normalized:
                return normalized

    combined = " ".join(line.text.strip() for line in lines)
    if _QR_FRAGMENT_RE.search(combined):
        return "QRコード"
    return None


def _payment_from_transaction_window(all_lines: list[OcrTextLine], block: str) -> str | None:
    if not all_lines or not any(line.box for line in all_lines):
        return None

    block_lines = _lines_in_block(all_lines, block)
    datetime_lines = [line for line in block_lines if _DATETIME_LINE_RE.search(line.text)]
    if not datetime_lines:
        return None

    anchor = min(datetime_lines, key=_line_y_center)
    y_start = _line_y_center(anchor) - 10
    y_end = y_start + 250

    later_datetimes = [
        line
        for line in all_lines
        if line.box
        and _line_y_center(line) > _line_y_center(anchor) + 30
        and _DATETIME_LINE_RE.search(line.text)
    ]
    if later_datetimes:
        y_end = _line_y_center(min(later_datetimes, key=_line_y_center)) - 5

    window_lines = [
        line for line in all_lines if line.box and y_start <= _line_y_center(line) <= y_end
    ]
    if not window_lines:
        return None
    return _payment_from_spatial_lines(window_lines)


def extract_paygate_payment_method(
    block: str,
    lines: list[OcrTextLine] | None = None,
) -> str | None:
    """Extract payment method from a Paygate screenshot transaction block."""
    normalized_block = normalize_paygate_ocr_text(block)

    for extractor in (
        _payment_from_inline_text,
        lambda value: _payment_from_line_order(
            [line.strip() for line in value.splitlines() if line.strip()]
        ),
        _payment_from_block_scan,
    ):
        result = extractor(normalized_block)
        if result:
            return result

    if lines:
        block_lines = _lines_in_block(lines, normalized_block)
        result = _payment_from_spatial_lines(block_lines)
        if result:
            return result
        result = _payment_from_transaction_window(lines, normalized_block)
        if result:
            return result

    return None
