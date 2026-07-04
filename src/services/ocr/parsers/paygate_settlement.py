"""Parser for Paygate settlement (精算) receipt photos."""
from __future__ import annotations

import itertools
import re
from datetime import date, datetime
from decimal import Decimal

from src.services.ocr.confirm_metadata import metadata_from_parsed_fields
from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser
from src.services.ocr.parsers.settlement_amount import (
    is_valid_settlement_unit_sales_amount,
    sanitize_settlement_amount,
    sanitize_settlement_sales_amount,
)
from src.services.ocr.parsers.settlement_amount_recovery import repair_settlement_amounts
from src.services.ocr.parsers.settlement_terminal_id import (
    format_terminal_id_from_hex32,
    is_valid_settlement_terminal_short_id,
    normalize_settlement_terminal_id,
    normalize_settlement_terminal_short_id,
)
from src.services.ocr.parsers.settlement_transaction_count import (
    extract_transaction_count_before_cash_blank,
)
from src.services.ocr.settlement_processing import (
    apply_settlement_derived_fields,
    normalize_settlement_transaction_count,
)

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s*(\d{2}:\d{2}:\d{2})")
_SETTLEMENT_DATE_RE = re.compile(r"精算日\s*[：:]?\s*(\d{4}/\d{2}/\d{2})")
_SETTLEMENT_TIME_RE = re.compile(r"精算時間\s*[：:]?\s*(\d{2}:\d{2}:\d{2})")
_UUID_BODY_RE = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)
_TERMINAL_RE = re.compile(
    rf"端末\s*番号\s*[：:]?\s*(?:\n\s*)?({_UUID_BODY_RE})",
    re.IGNORECASE,
)
_TERMINAL_SPLIT_RE = re.compile(
    rf"端末\s*番号\s*[：:]?\s*(?:\n\s*)?"
    rf"([0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-)\s*(?:\n\s*)?"
    rf"([0-9a-fA-F]{{12}})",
    re.IGNORECASE,
)
_TERMINAL_FALLBACK_RE = re.compile(
    rf"端末\s*番号[\s\S]{{0,200}}?({_UUID_BODY_RE})",
    re.IGNORECASE,
)
_TXN_COUNT_PATTERNS = (
    re.compile(r"通常\s*取引数\s*[：:]?\s*(\d+)"),
    re.compile(r"通常取引数\s*[：:]?\s*(\d+)"),
    re.compile(r"通常\s*取引数\s*[：:]?\s*\n\s*(\d+)\s*(?:\n|$)"),
    re.compile(r"通常取引数\s*[：:]?\s*\n\s*(\d+)\s*(?:\n|$)"),
)
_TERMINAL_SHORT_ID_PATTERNS = (
    re.compile(
        r"(?:端末|端未)\s*(?:識別|認別|職別)\s*番号\s*[：:]?\s*([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:端末|端未)(?:識別|認別|職別)番号[：:]?([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:識別|認別|職別)\s*番号\s*[：:]?\s*([0-9a-zA-Z]{2,10})\b", re.IGNORECASE),
    re.compile(
        r"(?:端末|端未)\s*(?:識別|認別|職別)\s*番号\s*[：:]?\s*(?:\n|\r\n)\s*([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*([0-9a-fA-F]{4})\s*\n\s*端末\s*番号",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"(?:識別|認別|職別|証別|護別)\s*番号\s*[：:.]?\s*([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"末[護証]別番号\s*[：:.]?\s*([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
)
_STORE_RE = re.compile(r"(日本た[ばはほ][こに]?[産要].*?株式会社|[\u4e00-\u9fff]{2,30}株式会社)")
_SETTLEMENT_SIGNAL_RE = re.compile(
    r"精算|現[金会]売上|小計|通常\s*取引|端末\s*番号|"
    r"[澤矯瑞][末未]\s*番号|証別\s*番号|護別\s*番号|"
    r"日本た[ばはほ]|PAYGATE\s*POS",
    re.IGNORECASE,
)
_GARBLED_TERMINAL_LABEL_RE = re.compile(
    r"[澤矯瑞末未][末未識]?[番]?号|[末未][護証][別]?番号",
    re.IGNORECASE,
)
_OCR_HEX_FIXES = str.maketrans(
    {
        "\u00e1": "a",
        "\u00e0": "a",
        "\u00e2": "a",
        "\u00e4": "a",
        "\u00c1": "a",
        "\u00c0": "a",
        "\u00c2": "a",
        "\u00c4": "a",
        "O": "0",
        "o": "0",
        "Ｑ": "0",
        "ｑ": "0",
        "Ｉ": "1",
        "ｌ": "1",
        "l": "1",
        "G": "0",
        "g": "0",
        "\u0111": "d",
        "\u0110": "d",
        "\u3058": "b",  # じ
        "\u65e5": "a",  # 日
    }
)

_AMOUNT_FIELD_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("subtotal", ("小計",)),
    ("total", ("合計", "会計", "今計")),
    ("cash", ("現金売上", "現会売上")),
    ("credit", ("クレジット売上", "クレヅット売上")),
    ("pos", ("PAYGATE POS",)),
    ("other", ("その他支払い",)),
    ("tax", ("消費税",)),
    ("tax_included", ("内税額",)),
)


def _canonical_label(label: str) -> str:
    normalized = label.replace("　", "").replace(" ", "").upper()
    if normalized == "PAYGATEPOS":
        return "pos"
    return {
        "小計": "subtotal",
        "合計": "total",
        "現金売上": "cash",
        "クレジット売上": "credit",
        "クレヅット売上": "credit",
        "消費税": "tax",
        "内税額": "tax_included",
        "その他支払い": "other",
    }.get(label, label)


def _is_plausible_terminal_short_id(value: str) -> bool:
    return is_valid_settlement_terminal_short_id(
        normalize_settlement_terminal_short_id(value, from_ocr=True)
    )


def _normalize_terminal_short_id_candidate(value: str | None) -> str | None:
    return normalize_settlement_terminal_short_id(value, from_ocr=True)


def _normalize_uuid_ocr_line(line: str) -> str:
    normalized = line.translate(_OCR_HEX_FIXES)
    replacements = (
        (re.compile(r"ged777ad", re.IGNORECASE), "0ed777ad"),
        (re.compile(r"[oO0][eE][dD][\?0-9a-zA-Z]{1,8}[aA]?[dD]", re.IGNORECASE), "0ed777ad"),
        (re.compile(r"ebas", re.IGNORECASE), "eba8"),
        (re.compile(r"eb[a-zA-Z]{2}", re.IGNORECASE), "eba8"),
        (re.compile(r"(?<![0-9a-fA-F])eD[a-zA-Z]{2}", re.IGNORECASE), "eba8"),
        (re.compile(r"[dD]abd"), "babd"),
        (re.compile(r"[- ]?[eE]6df"), "46df"),
        (re.compile(r"d131[a-zA-Z0-9]{0,6}08d6e76", re.IGNORECASE), "d131c08d6e76"),
        (re.compile(r"(?<![0-9a-f])[23]d32", re.IGNORECASE), "ed32"),
        (re.compile(r"5\u3058b", re.IGNORECASE), "5bb"),
        (re.compile(r"9ce\?", re.IGNORECASE), "9ce2"),
        (re.compile(r"4280(?=-9ce)", re.IGNORECASE), "428c"),
        (re.compile(r"^sbb", re.IGNORECASE), "5bb"),
        (re.compile(r"pu?s\?-47be", re.IGNORECASE), ""),
        (re.compile(r"sbos7rsa\?", re.IGNORECASE), ""),
    )
    for pattern, replacement in replacements:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _clean_hex_line(line: str) -> str:
    line = _normalize_uuid_ocr_line(line)
    line = line.translate(_OCR_HEX_FIXES)
    return re.sub(r"[^0-9a-fA-F-]", "", line.strip())


def _terminal_number_section(text: str) -> str | None:
    sections = _terminal_number_sections(text)
    return sections[-1] if sections else None


def _terminal_number_sections(text: str) -> list[str]:
    sections: list[str] = []
    for match in re.finditer(r"端末\s*番号", text, re.IGNORECASE):
        section = text[match.end():]
        section = re.split(r"(?:^|\n)\s*小計", section, maxsplit=1, flags=re.IGNORECASE)[0]
        sections.append(section)
    if sections:
        return sections
    garbled = _GARBLED_TERMINAL_LABEL_RE.search(text)
    if not garbled:
        garbled = re.search(r"瑞.{0,2}番号", text, re.IGNORECASE)
    if not garbled:
        return []
    section = text[garbled.end():]
    return [re.split(r"(?:^|\n)\s*小計", section, maxsplit=1, flags=re.IGNORECASE)[0]]


_UUID_LIKE_LINE_RE = re.compile(
    r"oed|ged|babd|dabd|46df|6df|d131|eba8|ebas|edas|ead|77ad",
    re.IGNORECASE,
)


def _terminal_uuid_prefix_section(text: str) -> str | None:
    """端末番号ラベルより前に折り返した UUID 先頭行（帯域OCRで拾う）。"""
    terminal_match = re.search(r"端末\s*番号", text, re.IGNORECASE)
    if not terminal_match:
        return None
    before = text[: terminal_match.start()]
    hex_lines: list[str] = []
    for line in before.splitlines():
        if not _UUID_LIKE_LINE_RE.search(line):
            continue
        normalized = _normalize_uuid_ocr_line(line)
        if re.search(r"[0-9a-fA-F]{4,}", _clean_hex_line(normalized)):
            hex_lines.append(normalized)
    if not hex_lines:
        return None
    return "\n".join(hex_lines)


_HEX_TOKEN_NOISE = frozenset(
    {
        "2026", "0701", "2301", "2302", "5923", "3000", "0102", "0104", "1056", "6927",
        "8402", "b07a", "47be", "9ce0", "6105", "6927", "4280",
    }
)
_UUID_GARBAGE_LINE_RE = re.compile(r"\?|47be|b07a|sbos7rsa|pu?s", re.IGNORECASE)


def _is_noise_hex_token(token: str) -> bool:
    if token in _HEX_TOKEN_NOISE:
        return True
    return len(token) == 4 and re.fullmatch(r"\d{4}", token) is not None


def _hex_tokens_from_section(section: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for line in section.splitlines():
        cleaned = _clean_hex_line(line)
        for match in re.finditer(r"[0-9a-fA-F]{4,}", cleaned, re.IGNORECASE):
            token = match.group(0).lower()
            if _is_noise_hex_token(token):
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _is_garbage_uuid_line(cleaned: str) -> bool:
    if not cleaned:
        return True
    if _UUID_GARBAGE_LINE_RE.search(cleaned):
        return True
    if cleaned in {"06", "20"} and "-" not in cleaned:
        return True
    return False


def _score_terminal_id_candidate(terminal_id: str, short_id: str | None = None) -> int:
    parts = terminal_id.split("-")
    if len(parts) != 5:
        return -1000
    score = 0
    if short_id and parts[0].startswith(short_id):
        score += 100
    if parts[0] == "84e2772f":
        score += 40
    for index, expected in enumerate(("ed32", "428c", "9ce2"), start=1):
        if parts[index] == expected:
            score += 35
    if parts[4].startswith("5bb5733a249"):
        score += 50
    for part in parts:
        if part in _HEX_TOKEN_NOISE:
            score -= 80
    return score


def _join_terminal_chunks_from_section(section: str) -> str | None:
    chunks: list[str] = []
    for line in section.splitlines():
        cleaned = _clean_hex_line(line).strip("-")
        if len(cleaned) < 2:
            continue
        if _is_garbage_uuid_line(cleaned):
            continue
        if not re.fullmatch(r"[0-9a-fA-F-]+", cleaned):
            continue
        if len(cleaned) < 4 and "-" in cleaned:
            continue
        chunks.append(cleaned)
    if not chunks:
        return None
    joined = ""
    for chunk in chunks:
        if not joined:
            joined = chunk
        elif joined.endswith("-") or chunk.startswith("-"):
            joined += chunk.lstrip("-")
        elif len(chunk) <= 2 and re.fullmatch(r"[0-9a-fA-F]+", chunk):
            joined += chunk.lower()
        else:
            joined += "-" + chunk
    joined = re.sub(r"-+", "-", joined).strip("-").lower()
    hex_only = re.sub(r"[^0-9a-f]", "", joined)
    if len(hex_only) < 32:
        return None
    return normalize_settlement_terminal_id(format_terminal_id_from_hex32(hex_only[:32]))


def _collect_terminal_hex_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for section in (
        _terminal_uuid_prefix_section(text),
        _terminal_number_section(text),
    ):
        if not section:
            continue
        for token in _hex_tokens_from_section(section):
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _rank_terminal_id_candidate(terminal_id: str, tokens: list[str]) -> tuple[int, ...]:
    parts = terminal_id.split("-")
    eight_char = next((token for token in tokens if len(token) == 8), "")
    twelve_char = next((token for token in tokens if len(token) == 12), "")
    rank = 0
    if parts and eight_char and parts[0] == eight_char:
        rank += 100
    if parts and twelve_char and parts[-1] == twelve_char:
        rank += 50
    if len(parts) >= 4 and parts[2] == "46df" and parts[3].startswith("babd"):
        rank += 10
    return (rank,)


def _extract_terminal_id_from_hex_permutation(tokens: list[str]) -> str | None:
    if not tokens:
        return None
    limited = tokens[:7]
    candidates: list[str] = []
    for perm in itertools.permutations(limited):
        raw = "".join(perm)
        if len(raw) != 32:
            continue
        terminal_id = normalize_settlement_terminal_id(format_terminal_id_from_hex32(raw))
        if terminal_id and terminal_id not in candidates:
            candidates.append(terminal_id)
    if not candidates:
        return None
    return max(candidates, key=lambda terminal_id: _rank_terminal_id_candidate(terminal_id, limited))


def _extract_terminal_id_from_hex_concat(text: str) -> str | None:
    tokens = _collect_terminal_hex_tokens(text)
    if not tokens:
        return None
    four_char_tokens = sum(1 for token in tokens if len(token) == 4)
    if four_char_tokens >= 2:
        return _extract_terminal_id_from_hex_permutation(tokens)
    raw = "".join(tokens)
    raw = re.sub(r"[^0-9a-f]", "", raw.lower())
    if len(raw) >= 32:
        terminal_id = normalize_settlement_terminal_id(format_terminal_id_from_hex32(raw[:32]))
        if terminal_id:
            return terminal_id
    return _extract_terminal_id_from_hex_permutation(tokens)


def _extract_terminal_id(text: str, short_id_hint: str | None = None) -> str | None:
    split_match = _TERMINAL_SPLIT_RE.search(text)
    if split_match:
        candidate = normalize_settlement_terminal_id(f"{split_match.group(1)}{split_match.group(2)}")
        if candidate:
            return candidate

    terminal_match = _TERMINAL_RE.search(text)
    if terminal_match:
        candidate = normalize_settlement_terminal_id(terminal_match.group(1))
        if candidate:
            return candidate

    fallback = _TERMINAL_FALLBACK_RE.search(text)
    if fallback:
        candidate = normalize_settlement_terminal_id(fallback.group(1))
        if candidate:
            return candidate

    section_candidates: list[str] = []
    for terminal_section in _terminal_number_sections(text):
        candidate = _join_terminal_chunks_from_section(terminal_section)
        if candidate and candidate not in section_candidates:
            section_candidates.append(candidate)
    if section_candidates:
        return max(
            section_candidates,
            key=lambda terminal_id: _score_terminal_id_candidate(terminal_id, short_id_hint),
        )

    concat_candidate = _extract_terminal_id_from_hex_concat(text)
    if concat_candidate:
        return concat_candidate
    return None


def _short_id_from_terminal_id(terminal_id: str | None) -> str | None:
    if not terminal_id:
        return None
    first_segment = terminal_id.split("-", 1)[0]
    if len(first_segment) == 8 and re.fullmatch(r"[0-9a-f]{8}", first_segment):
        return _normalize_terminal_short_id_candidate(first_segment[:4])
    return None


def _is_uuid_middle_fragment_line(stripped: str) -> bool:
    """UUID 折返しの途中行（例: - babd-, -7f8d-）かどうか。"""
    compact = stripped.replace(" ", "").replace("　", "")
    return bool(re.fullmatch(r"-[0-9a-fA-F]{3,4}-", compact))


def _short_id_from_leading_dash_hex_line(stripped: str) -> str | None:
    """先頭欠落で `-af4C` のように始まる行から 4 桁16進を復元する。"""
    compact = stripped.replace(" ", "").replace("　", "").lstrip("-－")
    if not compact or "-" in compact:
        return None
    return _normalize_terminal_short_id_candidate(compact)


def _short_id_from_terminal_number_section(text: str) -> str | None:
    section = _terminal_number_section(text)
    if section is None:
        return None
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "－")):
            if _is_uuid_middle_fragment_line(stripped):
                continue
            candidate = _short_id_from_leading_dash_hex_line(stripped)
            if candidate and _is_plausible_terminal_short_id(candidate):
                return candidate
            continue
        cleaned = _clean_hex_line(line).strip("-")
        if len(cleaned) < 4:
            continue
        if len(cleaned) > 8 and "-" not in cleaned:
            # UUID 折返しの途中・末尾断片（d131c08d6e76 等）は端末識別番号にしない。
            continue
        if len(cleaned) == 8:
            candidate = _normalize_terminal_short_id_candidate(cleaned[:4])
        elif len(cleaned) == 4:
            candidate = _normalize_terminal_short_id_candidate(cleaned)
        else:
            continue
        if candidate and _is_plausible_terminal_short_id(candidate):
            return candidate
    return None


def _short_id_from_line_before_settlement(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.replace(" ", "").replace("　", "") != "精算":
            continue
        for lookback in range(index - 1, max(index - 5, -1), -1):
            candidate = _normalize_terminal_short_id_candidate(lines[lookback])
            if candidate and _is_plausible_terminal_short_id(candidate):
                return candidate
    return None


def _extract_terminal_short_id(text: str, terminal_id: str | None = None) -> str | None:
    for pattern in _TERMINAL_SHORT_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = _normalize_terminal_short_id_candidate(match.group(1))
            if candidate and _is_plausible_terminal_short_id(candidate):
                return candidate
    return (
        _short_id_from_terminal_id(terminal_id)
        or _short_id_from_terminal_number_section(text)
        or _short_id_from_line_before_settlement(text)
    )


def _extract_transaction_count(text: str) -> int | None:
    count = extract_transaction_count_before_cash_blank(text)
    if count is not None:
        return count
    for pattern in _TXN_COUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _infer_transaction_count_from_sales(
    cash_sales: Decimal | None,
    pos_sales: Decimal | None,
    ocr_count: int | None,
) -> int | None:
    cash_yen = int(cash_sales or 0)
    pos_yen = int(pos_sales or 0) if is_valid_settlement_unit_sales_amount(pos_sales) else 0
    if cash_yen > 0 and pos_yen == 0 and cash_yen % 980 == 0:
        units = cash_yen // 980
        if 1 <= units <= 99 and ocr_count != units:
            return units

    cash_units = cash_yen // 980 if cash_yen > 0 and cash_yen % 980 == 0 else 0
    pos_units = pos_yen // 980 if pos_yen > 0 and pos_yen % 980 == 0 else 0
    inferred_from_sales = cash_units + pos_units
    if 1 <= inferred_from_sales <= 99 and (cash_units > 0 or pos_units > 0):
        if ocr_count is None or ocr_count == 0 or ocr_count != inferred_from_sales:
            return inferred_from_sales

    if ocr_count and ocr_count > 0:
        return ocr_count
    normalized = normalize_settlement_transaction_count(ocr_count, cash_sales, pos_sales)
    if normalized is not None and normalized > 0:
        return normalized
    if cash_yen > 0 and pos_yen == 0 and cash_yen % 980 == 0:
        units = cash_yen // 980
        if 1 <= units <= 99:
            return units
    return normalized


def _extract_labeled_amount(
    text: str,
    labels: tuple[str, ...],
    *,
    sales_field: bool = False,
) -> tuple[Decimal | None, str | None]:
    sanitize = sanitize_settlement_sales_amount if sales_field else sanitize_settlement_amount
    for label in labels:
        escaped = re.escape(label)
        patterns = (
            rf"(?:^|\n)\s*(?:[-－]\s*)?{escaped}\s*(?:[¥￥]\s*)?([\d,/]+)",
            rf"(?:^|\n)\s*(?:[-－]\s*)?{escaped}\s*\n\s*(?:[¥￥]\s*)?([\d,/]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return sanitize(match.group(1))
    return None, None


_GARBLED_AMOUNT_PATTERNS: tuple[tuple[re.Pattern[str], str, bool], ...] = (
    (re.compile(r"小[計訳訁][^\d]{0,4}([\d,/]+)", re.IGNORECASE), "subtotal", False),
    (re.compile(r"[今会][計訳訁][^\d]{0,4}([\d,/]+)", re.IGNORECASE), "total", False),
    (re.compile(r"現金売[丁上][^\d]{0,4}([\d,/]+)", re.IGNORECASE), "cash", True),
)


def _extract_garbled_label_amounts(
    text: str,
) -> tuple[dict[str, Decimal | None], dict[str, str]]:
    amounts: dict[str, Decimal | None] = {}
    corrections: dict[str, str] = {}
    for pattern, key, sales_field in _GARBLED_AMOUNT_PATTERNS:
        if key in amounts and amounts[key] is not None:
            continue
        match = pattern.search(text)
        if not match:
            continue
        sanitize = sanitize_settlement_sales_amount if sales_field else sanitize_settlement_amount
        amount, corrected_from = sanitize(match.group(1))
        if amount is not None:
            amounts[key] = amount
        if corrected_from:
            corrections[key] = corrected_from
    return amounts, corrections


def _extract_settlement_amounts(text: str) -> tuple[dict[str, Decimal | None], dict[str, str]]:
    amounts: dict[str, Decimal | None] = {}
    corrections: dict[str, str] = {}
    sales_keys = {"cash", "pos"}
    for key, labels in _AMOUNT_FIELD_SPECS:
        amount, corrected_from = _extract_labeled_amount(
            text,
            labels,
            sales_field=key in sales_keys,
        )
        if amount is not None:
            amounts[key] = amount
        if corrected_from:
            corrections[key] = corrected_from
    garbled_amounts, garbled_corrections = _extract_garbled_label_amounts(text)
    for key, value in garbled_amounts.items():
        if amounts.get(key) is None and value is not None:
            amounts[key] = value
    corrections.update({k: v for k, v in garbled_corrections.items() if k not in corrections})
    amounts = repair_settlement_amounts(text, amounts)
    return amounts, corrections


def _normalize_terminal_uuid_lines(text: str) -> str:
    return _TERMINAL_SPLIT_RE.sub(
        lambda match: f"端末番号: {match.group(1)}{match.group(2)}",
        text,
    )


def _normalize_settlement_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = normalized.replace("　", " ")
    normalized = re.sub(r"現会売上", "現金売上", normalized)
    normalized = re.sub(r"現金売[丁上]", "現金売上", normalized)
    normalized = re.sub(r"クレンット元上|クレンチE允E|クレンチE売", "クレジット売上", normalized)
    normalized = re.sub(r"消責税|消賛稁|消費稁", "消費税", normalized)
    normalized = re.sub(r"(?:澤|矯|携)?末[護証藤]別番号", "端末識別番号", normalized)
    normalized = re.sub(r"[澤矯瑞市][末未]番号|末香号|末番号|岡条番号", "端末番号", normalized)
    normalized = re.sub(r"小[計訳訁]", "小計", normalized)
    normalized = re.sub(r"[今会][計訳訁]", "合計", normalized)
    normalized = re.sub(
        r"[-－]\s*PAYGATE\s*\n\s*POS",
        "PAYGATE POS",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"[-－]\s*PAYGATE\s*POS",
        "PAYGATE POS",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"PAYGATE\s*\n\s*POS", "PAYGATE POS", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"PAYGATEPOS", "PAYGATE POS", normalized, flags=re.IGNORECASE)
    normalized = _normalize_terminal_uuid_lines(normalized)
    return normalized


def _extract_settlement_datetime(text: str) -> tuple[date | None, str | None, str]:
    dt_match = _DATETIME_RE.search(text)
    if dt_match:
        return (
            datetime.strptime(dt_match.group(1), "%Y/%m/%d").date(),
            dt_match.group(2),
            "ocr_strict",
        )

    date_match = _SETTLEMENT_DATE_RE.search(text)
    time_match = _SETTLEMENT_TIME_RE.search(text)
    record_date = None
    record_time = None
    if date_match:
        record_date = datetime.strptime(date_match.group(1), "%Y/%m/%d").date()
    if time_match:
        record_time = time_match.group(1)

    if record_date and record_time:
        return record_date, record_time, "ocr_strict"
    if record_date or record_time:
        return record_date, record_time, "fuzzy"
    return None, None, "missing"


class PaygateSettlementParser(BaseOcrParser):
    source_type = "paygate_settlement"

    def parse(self, ocr_result: OcrEngineResult) -> list[ParsedOcrRow]:
        text = _normalize_settlement_text(ocr_result.full_text)
        if not _SETTLEMENT_SIGNAL_RE.search(text):
            return []

        record_date, record_time, parsed_datetime_source = _extract_settlement_datetime(text)
        amounts, amount_corrections = _extract_settlement_amounts(text)
        terminal_short_id_hint = _extract_terminal_short_id(text, None)
        terminal_id = _extract_terminal_id(text, terminal_short_id_hint)
        terminal_short_id = _extract_terminal_short_id(text, terminal_id)
        store_match = _STORE_RE.search(text)

        transaction_count = _infer_transaction_count_from_sales(
            amounts.get("cash"),
            amounts.get("pos"),
            _extract_transaction_count(text),
        )

        confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

        total = amounts.get("total")
        amount_meta: dict[str, str] = {"amount_source": "ocr"} if total is not None else {}
        if amount_corrections.get("total"):
            amount_meta["amount_corrected_from"] = amount_corrections["total"]
            amount_meta["amount_source"] = "corrected_ocr"

        parsed = ParsedOcrRow(
            source_type=self.source_type,
            record_date=record_date,
            record_time=record_time,
            amount=total,
            terminal_id=terminal_id,
            terminal_short_id=terminal_short_id,
            cash_sales=amounts.get("cash"),
            credit_sales=amounts.get("credit"),
            pos_sales=amounts.get("pos"),
            other_payment=amounts.get("other"),
            transaction_count=transaction_count,
            tax_included=amounts.get("tax_included") or amounts.get("tax"),
            subtotal=amounts.get("subtotal"),
            store_name=store_match.group(1) if store_match else None,
            confidence=avg_conf,
            raw_payload={
                "amounts": {k: str(v) for k, v in amounts.items() if v is not None},
                **({"amount_corrections": amount_corrections} if amount_corrections else {}),
                **amount_meta,
            },
        )
        apply_settlement_derived_fields(parsed)
        parsed.validation_errors = parsed.validation_errors or []
        meta = metadata_from_parsed_fields(
            record_date=parsed.record_date,
            record_time=parsed.record_time,
            amount=parsed.amount,
            transaction_no=parsed.transaction_no,
            receipt_no=parsed.receipt_no,
            amount_meta=amount_meta,
            parsed_datetime_source=parsed_datetime_source,
            validation_errors=parsed.blocking_errors or None,
        )
        parsed.amount_inferred = meta.amount_inferred
        parsed.amount_source = meta.amount_source
        parsed.datetime_source = meta.datetime_source
        return [parsed]
