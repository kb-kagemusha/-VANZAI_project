"""Field-level OCR confidence for settlement receipts (reference display only)."""
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


def _label_line_confidence(lines: list[OcrTextLine], *labels: str) -> float | None:
    lowered_labels = [label.lower() for label in labels]
    matched: list[OcrTextLine] = []
    for line in lines:
        text = line.text.lower()
        if any(label in text for label in lowered_labels):
            matched.append(line)
    if not matched:
        return None
    return clamp_confidence(_average_confidence(matched))


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
    """Return (field_confidence, field_sources) for raw_payload / API."""
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
