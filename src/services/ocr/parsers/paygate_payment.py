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
_TXN_IN_BLOCK_RE = re.compile(r"(?<!\d)(1\d{6})(?!\d)")
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


def count_payment_labels_in_block(block: str) -> int:
    return len(list(_PAYMENT_LABEL_FLEX_RE.finditer(block)))


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


def _transaction_payment_region(block: str, transaction_no: str | None) -> str:
    """Limit payment extraction to the current transaction, not prior/next rows."""
    if not transaction_no:
        return block
    start = block.find(transaction_no)
    if start < 0:
        return block
    segment = block[start:]
    later = _TXN_IN_BLOCK_RE.search(segment[len(transaction_no) :])
    if later:
        segment = segment[: len(transaction_no) + later.start()]
    return segment


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


def _label_indexes_after_transaction(
    block_lines: list[str],
    transaction_no: str | None,
) -> list[int]:
    start = 0
    if transaction_no:
        for index, line in enumerate(block_lines):
            if transaction_no in line:
                start = index
                break
    return [
        index
        for index, line in enumerate(block_lines)
        if index >= start and _is_payment_label_line(line)
    ]


def _payment_tail_after_last_label(region: str, transaction_no: str | None = None) -> str:
    region_lines = [line.strip() for line in region.splitlines() if line.strip()]
    label_indexes = _label_indexes_after_transaction(region_lines, transaction_no)
    if not label_indexes:
        labels = list(_PAYMENT_LABEL_FLEX_RE.finditer(region))
        if not labels:
            return region
        last = labels[-1]
        return region[last.end() : last.end() + 120]
    label_index = label_indexes[0]
    tail_lines = region_lines[label_index + 1 : label_index + 5]
    return "\n".join(tail_lines)


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


def _payment_from_line_order(block_lines: list[str], transaction_no: str | None = None) -> str | None:
    for index in _label_indexes_after_transaction(block_lines, transaction_no):
        line = block_lines[index]
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


def _payment_from_block_scan(block: str, transaction_no: str | None = None) -> str | None:
    if not _block_has_payment_label(block):
        return None

    tail = _payment_tail_after_last_label(block, transaction_no)
    if _QR_FRAGMENT_RE.search(tail) or "QRコード" in tail.replace(" ", ""):
        return "QRコード"
    for method in ("現金", "クレジット"):
        if re.search(rf"(?<![\w]){method}(?![\w])", tail):
            return method
    return None


def _payment_from_spatial_lines(
    lines: list[OcrTextLine],
    transaction_no: str | None = None,
    block: str | None = None,
) -> str | None:
    region_lines = lines
    label_line: OcrTextLine | None = None
    if block:
        block_lines = [line.strip() for line in block.splitlines() if line.strip()]
        label_indexes = _label_indexes_after_transaction(block_lines, transaction_no)
        if label_indexes:
            canonical_text = block_lines[label_indexes[0]]
            for line in region_lines:
                if line.text.strip() == canonical_text:
                    label_line = line
                    break
    if label_line is None:
        label_candidates = [line for line in region_lines if _is_payment_label_line(line.text)]
        label_line = label_candidates[0] if label_candidates else None
    if label_line is None:
        return None

    for label in (label_line,):
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

    combined = " ".join(line.text.strip() for line in lines)
    if _QR_FRAGMENT_RE.search(combined):
        return "QRコード"
    return None


def _payment_from_transaction_window(
    all_lines: list[OcrTextLine],
    block: str,
    transaction_no: str | None = None,
) -> str | None:
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
    return _payment_from_spatial_lines(window_lines, transaction_no, block)


def _spatial_value_lines_for_label(
    label_line: OcrTextLine,
    lines: list[OcrTextLine],
) -> list[OcrTextLine]:
    ref_y = _line_y_center(label_line)
    ref_x = _line_x_center(label_line)
    candidates: list[OcrTextLine] = []

    split = _PAYMENT_LABEL_SPLIT_RE.match(label_line.text.strip())
    if split and split.group(3).strip():
        candidates.append(label_line)

    for line in lines:
        if line is label_line:
            continue
        if abs(_line_y_center(line) - ref_y) <= 28 and _line_x_center(line) > ref_x + 20:
            candidates.append(line)
    return candidates


def payment_method_confidence_from_lines(
    lines: list[OcrTextLine],
    block: str,
    payment_method: str,
    transaction_no: str | None,
) -> tuple[float | None, str]:
    """Confidence from the OCR line(s) paired with this transaction's 決済方法 label."""
    region = _transaction_payment_region(block, transaction_no)
    region_lines = _lines_in_block(lines, region)
    block_lines = [line.strip() for line in region.splitlines() if line.strip()]
    label_indexes = _label_indexes_after_transaction(block_lines, transaction_no)
    if not label_indexes:
        return None, "ocr_inferred"

    canonical_label_text = block_lines[label_indexes[0]]
    label_lines = [line for line in region_lines if line.text.strip() == canonical_label_text]
    if not label_lines:
        label_lines = [line for line in region_lines if _is_payment_label_line(line.text)]
    if not label_lines:
        return None, "ocr_inferred"

    label_line = label_lines[0]
    value_lines = _spatial_value_lines_for_label(label_line, region_lines)
    ocr_methods = [
        method
        for method in (_normalize_from_raw_text(line.text) for line in value_lines)
        if method
    ]
    if ocr_methods and payment_method not in ocr_methods:
        return 0.68, "ocr_inferred"

    matched_value_lines = [
        line for line in value_lines if normalize_paygate_payment_method(line.text) == payment_method
    ]
    if not matched_value_lines:
        return 0.72, "ocr_inferred"

    confidences = [line.confidence for line in matched_value_lines if line.confidence > 0]
    if not confidences:
        return 0.72, "ocr_inferred"
    avg = sum(confidences) / len(confidences)
    return max(0.0, min(1.0, round(avg, 4))), "ocr_line_direct"


def extract_paygate_payment_method(
    block: str,
    lines: list[OcrTextLine] | None = None,
    *,
    transaction_no: str | None = None,
) -> str | None:
    """Extract payment method from a Paygate screenshot transaction block."""
    normalized_block = normalize_paygate_ocr_text(block)
    region = _transaction_payment_region(normalized_block, transaction_no)
    region_lines = [line.strip() for line in region.splitlines() if line.strip()]

    for extractor in (
        lambda value: _payment_from_inline_text(value),
        lambda value: _payment_from_line_order(region_lines, transaction_no),
        lambda value: _payment_from_block_scan(value, transaction_no),
    ):
        result = extractor(region)
        if result:
            return result

    if lines:
        scoped_lines = _lines_in_block(lines, region)
        result = _payment_from_spatial_lines(scoped_lines, transaction_no, region)
        if result:
            return result
        result = _payment_from_transaction_window(lines, region, transaction_no)
        if result:
            return result

    return None
