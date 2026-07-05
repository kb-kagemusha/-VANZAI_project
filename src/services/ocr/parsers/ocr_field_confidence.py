"""Field-level OCR confidence for receipt rows (reference display only)."""
from __future__ import annotations

from typing import Any

from src.services.ocr.models import OcrEngineResult, OcrTextLine, ParsedOcrRow

# Display tiers (UI): >=0.99 black, 0.90-0.989 blue, <0.90 orange
CONFIDENCE_SOURCE_WEIGHTS: dict[str, float] = {
    "ocr_line_direct": 1.0,
    "ocr_line_pair": 0.96,
    "ocr_explicit": 0.94,
    "ocr_split": 0.92,
    "ocr_assembled": 0.82,
    "ocr_inferred": 0.68,
    "ocr_corrected": 0.78,
    "manual": 1.0,
}


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def confidence_tone(value: float | None) -> "high" | "medium" | "low" | "unknown":
    if value is None:
        return "unknown"
    if value >= 0.99:
        return "high"
    if value >= 0.90:
        return "medium"
    return "low"


def _average_confidence(lines: list[OcrTextLine]) -> float:
    confidences = [line.confidence for line in lines if line.confidence > 0]
    if not confidences:
        return 0.5
    return sum(confidences) / len(confidences)


def _confidence_from_lines(lines: list[OcrTextLine]) -> float | None:
    if not lines:
        return None
    return clamp_confidence(_average_confidence(lines))


def _lines_matching_snippets(lines: list[OcrTextLine], *snippets: str) -> list[OcrTextLine]:
    lowered_snippets = [snippet.lower() for snippet in snippets if snippet]
    if not lowered_snippets:
        return []
    matched: list[OcrTextLine] = []
    for line in lines:
        text = line.text.lower()
        if any(snippet in text for snippet in lowered_snippets):
            matched.append(line)
    return matched


def _lines_for_block(lines: list[OcrTextLine], block: str) -> list[OcrTextLine]:
    if not block.strip():
        return lines
    block_lower = block.lower()
    matched = [
        line
        for line in lines
        if line.text.strip() and line.text.strip().lower() in block_lower
    ]
    return matched if matched else lines


def _label_line_confidence(lines: list[OcrTextLine], *labels: str) -> float | None:
    return _confidence_from_lines(_lines_matching_snippets(lines, *labels))


def _amount_confidence(
    lines: list[OcrTextLine],
    amount_meta: dict[str, Any],
    *,
    label: str,
) -> tuple[float | None, str]:
    if amount_meta.get("amount_source") == "corrected_ocr":
        base = _label_line_confidence(lines, label) or 0.72
        return clamp_confidence(base * CONFIDENCE_SOURCE_WEIGHTS["ocr_corrected"]), "ocr_corrected"
    value = _label_line_confidence(lines, label)
    if value is None:
        return None, "ocr_inferred"
    return value, "ocr"


def build_settlement_field_confidence(
    ocr_result: OcrEngineResult,
    parsed: ParsedOcrRow,
    *,
    terminal_meta: dict[str, Any] | None = None,
    amount_meta: dict[str, Any] | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Return (field_confidence, field_sources) for settlement rows."""
    terminal_meta = terminal_meta or {}
    amount_meta = amount_meta or (parsed.raw_payload or {})
    lines = ocr_result.lines

    field_confidence: dict[str, float] = {}
    field_sources: dict[str, str] = {}

    if parsed.terminal_id:
        source = str(terminal_meta.get("source") or "ocr_assembled")
        base = float(terminal_meta.get("line_confidence") or _average_confidence(lines))
        weight = CONFIDENCE_SOURCE_WEIGHTS.get(source, CONFIDENCE_SOURCE_WEIGHTS["ocr_assembled"])
        penalty = float(terminal_meta.get("normalization_penalty") or 0.0)
        field_confidence["terminal_id"] = clamp_confidence(base * weight - penalty)
        field_sources["terminal_id"] = source

    if parsed.terminal_short_id:
        short_source = str(terminal_meta.get("short_id_source") or "ocr_line_direct")
        short_base = float(
            terminal_meta.get("short_id_line_confidence")
            or _label_line_confidence(lines, "端末識別", "識別番号")
            or field_confidence.get("terminal_id", 0.75)
        )
        short_weight = CONFIDENCE_SOURCE_WEIGHTS.get(short_source, 0.85)
        field_confidence["terminal_short_id"] = clamp_confidence(short_base * short_weight)
        field_sources["terminal_short_id"] = short_source

    for field_name, label in (
        ("amount", "合計"),
        ("subtotal", "小計"),
        ("cash_sales", "現金売上"),
        ("pos_sales", "paygate"),
    ):
        value = getattr(parsed, field_name, None)
        if value is None:
            continue
        conf, source = _amount_confidence(lines, amount_meta, label=label)
        if conf is not None:
            field_confidence[field_name] = conf
            field_sources[field_name] = source

    if parsed.record_date and parsed.record_time:
        dt_conf = _label_line_confidence(lines, "精算", parsed.record_date.isoformat().replace("-", "/"))
        if dt_conf is not None:
            field_confidence["record_datetime"] = dt_conf
            field_sources["record_datetime"] = (
                "ocr_line_direct" if parsed.datetime_source == "ocr_strict" else "ocr_inferred"
            )

    if parsed.transaction_count is not None:
        txn_conf = _label_line_confidence(lines, "通常取引数", "取引数")
        if txn_conf is not None:
            field_confidence["transaction_count"] = txn_conf
            field_sources["transaction_count"] = "ocr_line_direct"

    if parsed.confidence:
        field_confidence.setdefault("_document_avg", clamp_confidence(float(parsed.confidence)))

    return field_confidence, field_sources


def build_paygate_screenshot_field_confidence(
    ocr_result: OcrEngineResult,
    parsed: ParsedOcrRow,
    *,
    amount_meta: dict[str, Any] | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Return (field_confidence, field_sources) for Paygate screenshot rows."""
    amount_meta = amount_meta or (parsed.raw_payload or {})
    block = str(amount_meta.get("block") or "")
    lines = _lines_for_block(ocr_result.lines, block)

    field_confidence: dict[str, float] = {}
    field_sources: dict[str, str] = {}

    if parsed.record_date or parsed.record_time:
        snippets: list[str] = []
        if parsed.record_date:
            snippets.append(parsed.record_date.isoformat().replace("-", "/"))
        if parsed.record_time:
            snippets.append(parsed.record_time)
        dt_lines = _lines_matching_snippets(lines, *snippets)
        dt_conf = _confidence_from_lines(dt_lines)
        if dt_conf is not None:
            source = "ocr_line_direct" if parsed.datetime_source == "ocr_strict" else "ocr_inferred"
            weight = CONFIDENCE_SOURCE_WEIGHTS[source]
            field_confidence["record_datetime"] = clamp_confidence(dt_conf * weight)
            field_sources["record_datetime"] = source

    if parsed.amount is not None:
        yen_lines = _lines_matching_snippets(lines, "¥", "￥", "円")
        if amount_meta.get("amount_source") == "corrected_ocr":
            base = _confidence_from_lines(yen_lines) or float(parsed.confidence or 0.72)
            field_confidence["amount"] = clamp_confidence(base * CONFIDENCE_SOURCE_WEIGHTS["ocr_corrected"])
            field_sources["amount"] = "ocr_corrected"
        elif yen_lines:
            field_confidence["amount"] = _confidence_from_lines(yen_lines) or 0.5
            field_sources["amount"] = "ocr_line_direct"
        else:
            field_confidence["amount"] = clamp_confidence(float(parsed.confidence or 0.5) * 0.82)
            field_sources["amount"] = "ocr_inferred"

    if parsed.transaction_no:
        txn_lines = _lines_matching_snippets(lines, "取引番号", parsed.transaction_no)
        txn_conf = _confidence_from_lines(txn_lines)
        if txn_conf is not None:
            has_label = any("取引番号" in line.text for line in txn_lines)
            field_confidence["transaction_no"] = txn_conf
            field_sources["transaction_no"] = "ocr_line_direct" if has_label else "ocr_inferred"

    if parsed.receipt_no:
        receipt_lines = _lines_matching_snippets(lines, "レシート番号", parsed.receipt_no)
        receipt_conf = _confidence_from_lines(receipt_lines)
        if receipt_conf is not None:
            has_label = any("レシート番号" in line.text for line in receipt_lines)
            field_confidence["receipt_no"] = receipt_conf
            field_sources["receipt_no"] = "ocr_line_direct" if has_label else "ocr_inferred"

    if parsed.payment_method:
        payment_lines = _lines_matching_snippets(lines, "決済方法", parsed.payment_method)
        payment_conf = _confidence_from_lines(payment_lines)
        if payment_conf is not None:
            has_label = any("決済方法" in line.text for line in payment_lines)
            field_confidence["payment_method"] = payment_conf
            field_sources["payment_method"] = "ocr_line_direct" if has_label else "ocr_inferred"

    if parsed.confidence:
        field_confidence.setdefault("_document_avg", clamp_confidence(float(parsed.confidence)))

    return field_confidence, field_sources
