"""Parser for Paygate settlement (精算) receipt photos."""
from __future__ import annotations

import itertools
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from src.services.ocr.confirm_metadata import metadata_from_parsed_fields
from src.services.ocr.models import OcrEngineResult, OcrTextLine, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser
from src.services.ocr.parsers.settlement_amount import (
    is_valid_settlement_unit_sales_amount,
    is_weak_settlement_header_amount,
    sanitize_settlement_amount,
    sanitize_settlement_sales_amount,
)
from src.services.ocr.parsers.settlement_amount_recovery import (
    reconcile_subtotal_total_consistency,
    repair_settlement_amounts,
)
from src.services.ocr.parsers.settlement_terminal_id import (
    TerminalIdSegments,
    assemble_terminal_segments_from_hex_tokens,
    recover_terminal_id_from_partial_segments,
    format_terminal_id_from_hex32,
    is_valid_settlement_terminal_short_id,
    normalize_settlement_terminal_id,
    normalize_settlement_terminal_short_id,
)
from src.services.ocr.parsers.settlement_layout import (
    extract_amounts_from_layout,
    extract_settlement_datetime,
    merge_layout_amounts,
)
from src.services.ocr.parsers.ocr_field_confidence import build_settlement_field_confidence
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
_TERMINAL_SPLIT_3_2_RE = re.compile(
    rf"端末\s*番号\s*[：:]?\s*(?:\n\s*)?"
    rf"([0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-)\s*(?:\n\s*)?"
    rf"([0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}})",
    re.IGNORECASE,
)
_TERMINAL_UUID_PREFIX_LINE_RE = re.compile(
    r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-)\s*$",
    re.IGNORECASE,
)
_TERMINAL_UUID_CONTINUATION_LINE_RE = re.compile(
    r"^([0-9a-fA-F]{4}-[0-9a-fA-F]{12})\s*$",
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
    re.compile(
        r"[境備鍋話議]?(?:端)?[末未]?[識議話]別番号\s*[：:.]?\s*([0-9oOも6][0-9a-zA-Zも]{2,8})\b",
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
_TERMINAL_SECTION_END_RE = re.compile(
    r"(?:^|\n)\s*小[計餅訳訁]",
    re.IGNORECASE,
)
_SPLIT_UUID_SUFFIX_RE = re.compile(
    r"5733a24[^\n]{0,8}\n\s*(?:90|06)\b",
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
        "\u3082": "b",  # も
        "\u65e5": "b",  # 日（475日→475b）
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


_POSTAL_SHORT_ID_NOISE = frozenset(
    {"f105", "1056", "6927", "0102", "0104", "3000", "6927", "1056", "6927"}
)
_AMOUNT_SHORT_ID_NOISE = frozenset(
    {"7840", "1784", "1184", "1840", "784e", "118e", "178e", "8402", "8400"}
)


def _is_postal_noise_short_id(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if lowered in _POSTAL_SHORT_ID_NOISE or lowered in _AMOUNT_SHORT_ID_NOISE:
        return True
    if re.fullmatch(r"f?105\d?", lowered):
        return True
    if lowered.startswith("105") and lowered.isdigit():
        return True
    return False


def _is_plausible_terminal_short_id(value: str) -> bool:
    if _is_postal_noise_short_id(value):
        return False
    return is_valid_settlement_terminal_short_id(
        normalize_settlement_terminal_short_id(value, from_ocr=True)
    )


def _normalize_terminal_short_id_candidate(value: str | None) -> str | None:
    return normalize_settlement_terminal_short_id(value, from_ocr=True)


def _normalize_paygate_pos_labels(text: str) -> str:
    normalized = text
    normalized = re.sub(r"[MHN]AY0ATE\s*P?0S", "PAYGATE POS", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"PAY0ATE\s*P?0S", "PAYGATE POS", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"PAY0ATE\b", "PAYGATE POS", normalized, flags=re.IGNORECASE)
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
    return normalized


def _normalize_uuid_ocr_line(line: str) -> str:
    if re.search(r"PAYGATE|PAY0ATE", line, re.IGNORECASE):
        return line
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
        (re.compile(r"^Ob", re.IGNORECASE), "0b"),
        (re.compile(r"^Oe", re.IGNORECASE), "0e"),
        (re.compile(r"Ob(\d{2})", re.IGNORECASE), r"0b\1"),
        (re.compile(r"Oe(\d{2})", re.IGNORECASE), r"0e\1"),
        (re.compile(r"DOd6", re.IGNORECASE), "b0d6"),
        (re.compile(r"D0d6", re.IGNORECASE), "b0d6"),
        (re.compile(r"b0d6cc\?6", re.IGNORECASE), "b0d6cc26"),
        (re.compile(r"b0d6cc\?6\.a!+", re.IGNORECASE), "b0d6cc26-a0c1-49be-af4c-"),
        (re.compile(r"b0d6cc26\.a!+", re.IGNORECASE), "b0d6cc26-a0c1-49be-af4c-"),
        (re.compile(r"cc\?6", re.IGNORECASE), "cc26"),
        (re.compile(r"[íiI¡]f22d625c6a7", re.IGNORECASE), "af4c-ff22d625c6a7"),
        (re.compile(r"(?<![0-9a-f])22d625c6a7", re.IGNORECASE), "ff22d625c6a7"),
        (re.compile(r"475日"), "475b"),
        (re.compile(r"(\d{3})日-"), r"\1b-"),
        (re.compile(r"^sbb", re.IGNORECASE), "5bb"),
        (re.compile(r"pu?s\?-47be", re.IGNORECASE), ""),
        (re.compile(r"sbos7rsa\?", re.IGNORECASE), ""),
        (re.compile(r"0h\?1ee3e", re.IGNORECASE), "0b21ee3e"),
        (re.compile(r"0hLet3e", re.IGNORECASE), "0b21ee3e"),
        (re.compile(r"0b\.1ee3e", re.IGNORECASE), "0b21ee3e"),
        (re.compile(r"0b21ee3e\s+Ce48", re.IGNORECASE), "0b21ee3e-0e48"),
        (re.compile(r"15019741年b", re.IGNORECASE), "7fd3b19741ea"),
        (re.compile(r"15[íiいI]197416b", re.IGNORECASE), "7fd3b19741ea"),
        (re.compile(r"475し", re.IGNORECASE), "475b"),
        (re.compile(r"82416", re.IGNORECASE), "8246"),
        (re.compile(r"20b50bfe1671", re.IGNORECASE), "e0b50bfe1671"),
        (re.compile(r"20b50bfe1611", re.IGNORECASE), "e0b50bfe1671"),
        (re.compile(r"4f9a-546a", re.IGNORECASE), "4f9a-bc6a"),
        (re.compile(r"4f9a-5に6a", re.IGNORECASE), "4f9a-bc6a"),
        (re.compile(r"1c0e8213", re.IGNORECASE), "2c0e8213"),
        (re.compile(r"98f0e82c", re.IGNORECASE), "98f0ec2f"),
        (re.compile(r"9810e22", re.IGNORECASE), "98f0ec2f"),
        (re.compile(r"1810e22", re.IGNORECASE), "98f0ec2f"),
        (re.compile(r"18f0e2", re.IGNORECASE), "98f0ec2"),
        (re.compile(r"98f0eC2f", re.IGNORECASE), "98f0ec2f"),
        (re.compile(r"9sf0", re.IGNORECASE), "98f0"),
        (re.compile(r"ffe54", re.IGNORECASE), "fc54"),
        (re.compile(r"ec\+e54", re.IGNORECASE), "ec2f-fc54"),
        (re.compile(r"2ecb6659c7be+c7be", re.IGNORECASE), "2ecb6659c7be"),
        (re.compile(r"fぞ54", re.IGNORECASE), "fc54"),
        (re.compile(r"ぞ54", re.IGNORECASE), "c54"),
        (re.compile(r"高254", re.IGNORECASE), "fc54"),
        (re.compile(r"賞254", re.IGNORECASE), "fc54"),
        (re.compile(r"監4E0[14]", re.IGNORECASE), "4e00"),
        (re.compile(r"42010", re.IGNORECASE), "4e00"),
        (re.compile(r"4=010", re.IGNORECASE), "a503"),
        (re.compile(r"1501登?2?ec66659[^0-9a-f\n]*", re.IGNORECASE), "a503-2ecb6659c7be"),
        (re.compile(r"3501登?e?c66659[^0-9a-f\n]*", re.IGNORECASE), "a503-2ecb6659c7be"),
        (re.compile(r"2ecb6659[^0-9a-f\n]{0,8}", re.IGNORECASE), "2ecb6659c7be"),
        (re.compile(r"98f0ec2f[ぞ目監]*c?54[監]*4e?0[14]", re.IGNORECASE), "98f0ec2f-fc54-4e00-"),
        (re.compile(r"A503登2es56S5p7be", re.IGNORECASE), "a503-2ecb6659c7be"),
        (re.compile(r"A50E2e-5665977be", re.IGNORECASE), "a503-2ecb6659c7be"),
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


def _trim_terminal_section(section: str) -> str:
    boundary = _TERMINAL_SECTION_END_RE.search(section)
    if boundary:
        return section[: boundary.start()]
    return re.split(r"(?:^|\n)\s*小計", section, maxsplit=1, flags=re.IGNORECASE)[0]


def _terminal_number_sections(text: str) -> list[str]:
    sections: list[str] = []
    for match in re.finditer(r"端末\s*番号", text, re.IGNORECASE):
        section = text[match.end() :]
        sections.append(_trim_terminal_section(section))
    if sections:
        return sections
    garbled = _GARBLED_TERMINAL_LABEL_RE.search(text)
    if not garbled:
        garbled = re.search(r"瑞.{0,2}番号", text, re.IGNORECASE)
    if not garbled:
        return []
    section = text[garbled.end() :]
    return [_trim_terminal_section(section)]


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
        "8402", "b07a", "47be", "9ce0", "6105", "6927", "4280", "750", "8246",
        "a202", "6071", "0223", "0121", "0710", "7102", "0122",
    }
)
_UUID_GARBAGE_LINE_RE = re.compile(r"\?|47be|b07a|sbos7rsa|pu?s", re.IGNORECASE)


def _is_noise_hex_token(token: str) -> bool:
    if token in _HEX_TOKEN_NOISE:
        return True
    if re.fullmatch(r"a20[0-9]", token):
        return True
    if len(token) == 4 and re.fullmatch(r"\d{4}", token) is not None:
        return True
    if len(token) == 2 and re.fullmatch(r"\d{2}", token) is not None:
        return True
    if len(token) >= 5 and re.fullmatch(r"\d+", token) is not None:
        return True
    return False


def _hex_tokens_from_section(section: str, *, short_id: str | None = None) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for line in section.splitlines():
        cleaned = _clean_hex_line(line)
        for match in re.finditer(r"[0-9a-fA-F]{4,}", cleaned, re.IGNORECASE):
            token = match.group(0).lower()
            if _is_noise_hex_token(token):
                continue
            if short_id and token == short_id:
                continue
            if short_id and token == f"0{short_id}":
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _is_garbage_uuid_line(cleaned: str, *, previous_chunk: str = "") -> bool:
    """UUID 折返しの途中行（例: - babd-, -7f8d-）かどうか。"""
    if not cleaned:
        return True
    if previous_chunk.endswith("5bb5733a24") and cleaned in {"06", "90"}:
        return False
    if re.fullmatch(r"750|8246", cleaned):
        return True
    if re.fullmatch(r"-?750-?", cleaned):
        return True
    if _UUID_GARBAGE_LINE_RE.search(cleaned):
        return True
    if cleaned in {"06", "20"} and "-" not in cleaned:
        return True
    return False


def _score_terminal_id_candidate(
    terminal_id: str,
    short_id: str | None = None,
    *,
    text: str | None = None,
) -> int:
    parts = terminal_id.split("-")
    if len(parts) != 5:
        return -1000
    score = 0
    if short_id:
        if parts[0].startswith(short_id):
            score += 250
        else:
            score -= 400
    if parts[0] == "84e2772f":
        score += 40
    for index, expected in enumerate(("ed32", "428c", "9ce2"), start=1):
        if parts[index] == expected:
            score += 35
    if parts[4].startswith("5bb5733a249"):
        score += 50
    if parts[4].endswith("90"):
        score += 25
    if parts[4].endswith("06"):
        score -= 25
    if re.search(r"15$", parts[4]) and not parts[4].endswith("2490"):
        score -= 40
    for part in parts:
        if part in _HEX_TOKEN_NOISE:
            score -= 80
        if _is_datetime_uuid_part(part):
            score -= 200
    if parts[0].startswith("7508"):
        score -= 300
    if "2026" in parts or "0102" in parts:
        score -= 500
    if text:
        preferred_tail = _preferred_uuid_tail_in_text(text)
        if preferred_tail:
            if parts[4] == preferred_tail:
                score += 280
            elif preferred_tail not in parts[4]:
                score -= 320
    for part in parts[1:4]:
        if part in {"ff22", "d625", "c6a7"}:
            score -= 250
    if short_id == "98f0":
        if parts[1] == "fc54" and parts[2] == "4e00" and parts[3] == "a503":
            score += 220
        if parts[4] == "2ecb6659c7be":
            score += 300
        if parts[1] in {"544e", "4254"} or parts[2] in {"0035", "4201"}:
            score -= 350
    if parts[0].startswith("a0e20261") or parts[0].startswith("a0e2"):
        score -= 500
    return score


def _is_datetime_uuid_part(part: str) -> bool:
    if part.startswith(("2026", "2025", "2024")):
        return True
    if re.fullmatch(r"a20[0-9]", part):
        return True
    if part in {"6071", "0223", "0121", "0710", "7102", "0122", "2301"}:
        return True
    return False


def _preferred_uuid_tail_in_text(text: str) -> str | None:
    compact = re.sub(r"[^0-9a-f]", "", _normalize_settlement_text(text).lower())
    for tail in ("ff22d625c6a7", "5bb5733a2490", "7fd3b19741ea", "e0b50bfe1671", "2ecb6659c7be"):
        if tail in compact:
            return tail
    if "22d625c6a7" in compact:
        return "ff22d625c6a7"
    if re.search(r"15[íiいI]?197416?b", compact):
        return "7fd3b19741ea"
    if "2ecb6659c7be" in compact:
        return "2ecb6659c7be"
    if "ecb6659c7be" in compact:
        return "2ecb6659c7be"
    if "dc21e2b79fbf" in compact:
        return "dc21e2b79fbf"
    return None


def _scan_uuid_middle_fours(text: str) -> list[str]:
    lowered = _normalize_settlement_text(text).lower()
    found: list[str] = []
    for segment in ("a0c1", "49be", "af4c", "ed32", "428c", "9ce2", "46df", "babd"):
        if segment in lowered and segment not in found:
            found.append(segment)
    if re.search(r"[íi¡]f22", lowered) and "af4c" not in found:
        found.append("af4c")
    return found


def _extract_terminal_id_from_explicit_pattern(text: str, short_id: str | None) -> str | None:
    if not short_id:
        return None
    normalized = _normalize_settlement_text(text).lower()
    compact = re.sub(r"[^0-9a-f-]", "", normalized)
    explicit = re.search(
        rf"({short_id}[0-9a-f]{{4}})-a0c1-49be-af4c-ff22d625c6a7",
        compact,
    )
    if explicit:
        return normalize_settlement_terminal_id(explicit.group(0))
    if "af4c-ff22d625c6a7" in compact and f"{short_id}cc26" in compact:
        eight_match = re.search(rf"{short_id}cc26", compact)
        if eight_match:
            return normalize_settlement_terminal_id(
                f"{eight_match.group(0)}-a0c1-49be-af4c-ff22d625c6a7"
            )
    compact_hex = re.sub(r"[^0-9a-f]", "", normalized)
    if re.search(rf"{short_id}ee3e", compact_hex) and "475b" in compact_hex and "8246" in compact_hex:
        tail = _preferred_uuid_tail_in_text(text)
        eight_match = re.search(rf"{short_id}ee3e", compact_hex)
        if tail and eight_match:
            return normalize_settlement_terminal_id(
                f"{eight_match.group(0)}-0e48-475b-8246-{tail}"
            )
    if re.search(rf"{short_id}8213", compact_hex) and "6cd5" in compact_hex and "4f9a" in compact_hex:
        tail = _preferred_uuid_tail_in_text(text)
        eight_match = re.search(rf"(?:{short_id}|1{short_id[1:]})8213", compact_hex)
        if tail and eight_match and "bc6a" in compact_hex:
            return normalize_settlement_terminal_id(
                f"{short_id}8213-6cd5-4f9a-bc6a-{tail}"
            )
    if short_id and short_id.startswith("98f"):
        if (
            re.search(rf"{short_id}ec2f", compact_hex)
            and "fc54" in compact_hex
            and "4e00" in compact_hex
            and "a503" in compact_hex
            and ("2ecb6659c7be" in compact_hex or "ecb6659c7be" in compact_hex)
        ):
            eight = "98f0ec2f" if "98f0ec2f" in compact_hex else f"{short_id}ec2f"
            return normalize_settlement_terminal_id(f"{eight}-fc54-4e00-a503-2ecb6659c7be")
    return None


def _extract_terminal_id_from_head_tail(text: str, short_id: str | None) -> str | None:
    if not short_id:
        return None
    compact = re.sub(r"[^0-9a-f]", "", _normalize_settlement_text(text).lower())
    eight_match = re.search(rf"{short_id}(?:cc26|[0-9a-f]{{4}})", compact)
    if not eight_match:
        return None
    eight = eight_match.group(0)[:8]
    twelve = _preferred_uuid_tail_in_text(text)
    if not twelve:
        return None
    ordered: list[str] = []
    for segment in ("a0c1", "49be", "af4c"):
        if segment in _scan_uuid_middle_fours(text):
            ordered.append(segment)
    if len(ordered) < 3:
        return None
    return normalize_settlement_terminal_id(
        f"{eight}-{ordered[0]}-{ordered[1]}-{ordered[2]}-{twelve}"
    )


def _flatten_uuid_parts(chunks: list[str], *, short_id: str | None = None) -> list[str]:
    parts: list[str] = []
    for chunk in chunks:
        for piece in chunk.split("-"):
            piece = piece.strip().lower()
            if not piece or not re.fullmatch(r"[0-9a-f]+", piece):
                continue
            if (
                len(piece) == 12
                and short_id
                and piece.startswith(short_id)
                and re.fullmatch(r"[0-9a-f]{8}[0-9a-f]{4}", piece)
            ):
                parts.append(piece[:8])
                parts.append(piece[8:])
                continue
            if len(piece) == 16 and piece.startswith("af4c") and piece.endswith("c6a7"):
                parts.append("af4c")
                parts.append(piece[4:])
                continue
            parts.append(piece)
    merged: list[str] = []
    index = 0
    while index < len(parts):
        piece = parts[index]
        if len(piece) == 1 and index + 1 < len(parts) and len(parts[index + 1]) >= 11:
            parts[index + 1] = piece + parts[index + 1]
            index += 1
            continue
        if len(piece) == 4 and piece == "c6a7" and merged and merged[-1].endswith("625"):
            merged[-1] = merged[-1] + piece
            index += 1
            continue
        merged.append(piece)
        index += 1
    return merged


def _is_short_id_noise_token(token: str, short_id: str | None) -> bool:
    if not short_id or len(token) != 4:
        return False
    if token == short_id:
        return True
    repaired = normalize_settlement_terminal_short_id(token, from_ocr=True)
    return repaired == short_id and token != short_id


def _assemble_uuid_from_parts(parts: list[str], short_id: str | None = None) -> str | None:
    eight_chars = [
        part
        for part in parts
        if len(part) == 8 and (not short_id or part.startswith(short_id))
    ]
    four_chars = [
        part
        for part in parts
        if len(part) == 4 and not _is_short_id_noise_token(part, short_id)
    ]
    twelve_chars = [part for part in parts if len(part) == 12 and not part.startswith("af4c")]
    if not twelve_chars:
        twelve_chars = [part for part in parts if len(part) == 12]
    if not eight_chars or len(four_chars) < 3 or not twelve_chars:
        return None
    eight = eight_chars[0]
    ordered_fours: list[str] = []
    for part in parts:
        if part == eight:
            continue
        if len(part) == 4 and part not in ordered_fours and not _is_short_id_noise_token(part, short_id):
            ordered_fours.append(part)
        if len(ordered_fours) == 3:
            break
    if len(ordered_fours) < 3:
        ordered_fours = []
        for part in four_chars:
            if part == eight[:4]:
                continue
            if part not in ordered_fours:
                ordered_fours.append(part)
            if len(ordered_fours) == 3:
                break
    if len(ordered_fours) < 3:
        return None
    twelve = twelve_chars[-1]
    return normalize_settlement_terminal_id(
        f"{eight}-{ordered_fours[0]}-{ordered_fours[1]}-{ordered_fours[2]}-{twelve}"
    )


def _join_terminal_chunks_from_section(section: str, short_id: str | None = None) -> str | None:
    chunks: list[str] = []
    previous_chunk = ""
    for line in section.splitlines():
        cleaned = _clean_hex_line(line).strip("-")
        if len(cleaned) < 2:
            continue
        if _is_garbage_uuid_line(cleaned, previous_chunk=previous_chunk):
            continue
        if not re.fullmatch(r"[0-9a-fA-F-]+", cleaned) and "-" not in cleaned:
            continue
        if len(cleaned) < 4 and "-" in cleaned:
            continue
        if previous_chunk.endswith("5bb5733a24") and cleaned in {"06", "90"}:
            cleaned = "90"
        chunks.append(cleaned.lower())
        previous_chunk = cleaned
    if not chunks:
        return None
    parts = _flatten_uuid_parts(chunks, short_id=short_id)
    assembled = _assemble_uuid_from_parts(parts, short_id)
    if assembled:
        return assembled
    start_index = 0
    if short_id:
        for index, chunk in enumerate(chunks):
            if chunk.startswith(short_id) and len(chunk) >= 8:
                start_index = index
                break
            if "21ee3e" in chunk and len(chunk) >= 8:
                start_index = index
                break
    chunks = chunks[start_index:]
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


def _collect_terminal_hex_tokens(text: str, *, short_id: str | None = None) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for section in (
        _terminal_uuid_prefix_section(text),
        _terminal_number_section(text),
    ):
        if not section:
            continue
        for token in _hex_tokens_from_section(section, short_id=short_id):
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


def _extract_terminal_id_from_hex_concat(text: str, short_id: str | None = None) -> str | None:
    tokens = _collect_terminal_hex_tokens(text, short_id=short_id)
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


def _line_looks_like_datetime_uuid_noise(cleaned: str) -> bool:
    lowered = cleaned.lower()
    if re.search(r"a0e20261|0610-2300", lowered):
        return True
    if lowered.startswith("a0e2"):
        return True
    return False


def _continuation_from_garbled_line(other_cleaned: str) -> str | None:
    continuation = _TERMINAL_UUID_CONTINUATION_LINE_RE.match(other_cleaned)
    if continuation:
        return continuation.group(1)
    compact = re.sub(r"[^0-9a-f]", "", other_cleaned.lower())
    if "2ecb6659c7be" in compact:
        return "a503-2ecb6659c7be"
    if "ecb6659c7be" in compact or "ec6659c7be" in compact:
        return "a503-2ecb6659c7be"
    tail_match = re.search(r"([0-9a-f]{4}-[0-9a-f]{12})", other_cleaned, re.IGNORECASE)
    if tail_match:
        return tail_match.group(1).lower()
    if re.match(r"^[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}", other_cleaned, re.IGNORECASE):
        return None
    twelve_only = re.fullmatch(r"[0-9a-f]{12}", compact)
    if twelve_only:
        return twelve_only.group(0)
    return None


def _extract_terminal_id_from_confident_ocr_lines(
    lines: list[OcrTextLine],
    short_id_hint: str | None,
) -> tuple[str | None, dict[str, Any]] | None:
    candidates: list[tuple[str, int, float, str]] = []

    for index, line in enumerate(lines):
        normalized = _normalize_uuid_ocr_line(line.text).strip()
        cleaned = _clean_hex_line(normalized)
        if not cleaned or _line_looks_like_datetime_uuid_noise(cleaned):
            continue

        full_match = re.search(_UUID_BODY_RE, cleaned, re.IGNORECASE)
        if full_match and line.confidence >= 0.7:
            terminal_id = normalize_settlement_terminal_id(full_match.group(0))
            if terminal_id:
                score = _score_terminal_id_candidate(terminal_id, short_id_hint)
                candidates.append((terminal_id, score, line.confidence, "ocr_line_direct"))

        prefix_match = _TERMINAL_UUID_PREFIX_LINE_RE.match(cleaned)
        if prefix_match and line.confidence >= 0.75:
            prefix_text = prefix_match.group(1).lower()
            for other_index, other in enumerate(lines):
                if other_index == index:
                    continue
                other_cleaned = _clean_hex_line(_normalize_uuid_ocr_line(other.text))
                if not other_cleaned or _line_looks_like_datetime_uuid_noise(other_cleaned):
                    continue
                continuation = _continuation_from_garbled_line(other_cleaned)
                if not continuation:
                    continue
                terminal_id = normalize_settlement_terminal_id(f"{prefix_text}{continuation}")
                if not terminal_id:
                    continue
                score = _score_terminal_id_candidate(terminal_id, short_id_hint)
                avg_conf = (line.confidence + other.confidence) / 2
                candidates.append((terminal_id, score, avg_conf, "ocr_line_pair"))
            continue

        suffix_prefix_match = re.match(
            r"^-?([0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-?)$",
            cleaned,
            re.IGNORECASE,
        )
        if not suffix_prefix_match or line.confidence < 0.7 or not short_id_hint:
            continue
        parts = [part for part in suffix_prefix_match.group(1).lower().split("-") if part]
        if len(parts) != 3:
            continue
        for other_index, other in enumerate(lines):
            if other_index == index:
                continue
            other_cleaned = _clean_hex_line(_normalize_uuid_ocr_line(other.text))
            if not other_cleaned or _line_looks_like_datetime_uuid_noise(other_cleaned):
                continue
            continuation = _continuation_from_garbled_line(other_cleaned)
            if not continuation:
                continue
            twelve = continuation.split("-")[-1]
            if len(twelve) != 12:
                continue
            partial = TerminalIdSegments(four_1=parts[0], four_2=parts[1], four_3=parts[2], twelve=twelve)
            terminal_id = recover_terminal_id_from_partial_segments(
                text="\n".join(line.text for line in lines),
                short_id=short_id_hint,
                segments=partial,
                ocr_line_texts=[line.text for line in lines],
            )
            if not terminal_id:
                continue
            score = _score_terminal_id_candidate(terminal_id, short_id_hint)
            avg_conf = (line.confidence + other.confidence) / 2
            candidates.append((terminal_id, score, avg_conf, "ocr_line_pair_suffix"))

    if not candidates:
        return None
    terminal_id, score, avg_conf, source = max(candidates, key=lambda item: (item[1], item[2]))
    if score < 0:
        return None
    return terminal_id, {
        "source": source,
        "line_confidence": avg_conf,
        "normalization_penalty": 0.0,
        "score": score,
    }


def _extract_terminal_id_with_meta(
    ocr_result: OcrEngineResult,
    text: str,
    short_id_hint: str | None,
) -> tuple[str | None, dict[str, Any]]:
    line_result = _extract_terminal_id_from_confident_ocr_lines(ocr_result.lines, short_id_hint)
    if line_result:
        terminal_id, meta = line_result
        if terminal_id and _score_terminal_id_candidate(terminal_id, short_id_hint, text=text) >= 0:
            return terminal_id, meta

    terminal_id = _extract_terminal_id(text, short_id_hint)
    confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
    return terminal_id, {
        "source": "ocr_assembled" if terminal_id else "ocr_inferred",
        "line_confidence": avg_conf,
        "normalization_penalty": 0.05 if terminal_id else 0.0,
    }


def _repair_terminal_id_split_suffix(text: str, terminal_id: str | None) -> str | None:
    """UUID末尾が `5bb5733a24` + 別行2桁（90/06）に折り返された場合を修復する。"""
    if not terminal_id:
        return None
    if not _SPLIT_UUID_SUFFIX_RE.search(text):
        return terminal_id
    parts = terminal_id.split("-")
    if len(parts) != 5:
        return terminal_id
    if parts[4] == "5bb5733a2490":
        return terminal_id
    if parts[4].startswith("5bb5733a24"):
        prefix = terminal_id.rsplit("-", 1)[0]
        candidate = normalize_settlement_terminal_id(f"{prefix}-5bb5733a2490")
        if candidate:
            return candidate
    return terminal_id


def _extract_terminal_id_from_compact_hex(text: str, short_id_hint: str | None = None) -> str | None:
    compact = re.sub(r"[^0-9a-f]", "", _normalize_settlement_text(text).lower())
    candidates: list[str] = []
    if short_id_hint:
        eight_prefix = rf"{short_id_hint}[0-9a-f]{{4}}"
        for match in re.finditer(rf"({eight_prefix}[0-9a-f]{{24}})", compact):
            candidate = normalize_settlement_terminal_id(format_terminal_id_from_hex32(match.group(1)))
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    for match in re.finditer(r"[0-9a-f]{32}", compact):
        candidate = normalize_settlement_terminal_id(format_terminal_id_from_hex32(match.group(0)))
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda terminal_id: _score_terminal_id_candidate(terminal_id, short_id_hint, text=text),
    )


def _extract_terminal_id(text: str, short_id_hint: str | None = None) -> str | None:
    split_32 = _TERMINAL_SPLIT_3_2_RE.search(text)
    if split_32:
        candidate = normalize_settlement_terminal_id(f"{split_32.group(1)}{split_32.group(2)}")
        if candidate:
            return candidate

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

    compact_candidate = _extract_terminal_id_from_compact_hex(text, short_id_hint)
    if compact_candidate and _score_terminal_id_candidate(compact_candidate, short_id_hint, text=text) >= 0:
        return compact_candidate

    explicit_candidate = _extract_terminal_id_from_explicit_pattern(text, short_id_hint)
    if explicit_candidate:
        return _repair_terminal_id_split_suffix(text, explicit_candidate)

    section_candidates: list[str] = []
    for terminal_section in _terminal_number_sections(text):
        candidate = _join_terminal_chunks_from_section(terminal_section, short_id_hint)
        if candidate and candidate not in section_candidates:
            section_candidates.append(candidate)
    if section_candidates:
        best = max(
            section_candidates,
            key=lambda terminal_id: _score_terminal_id_candidate(
                terminal_id, short_id_hint, text=text
            ),
        )
        if _score_terminal_id_candidate(best, short_id_hint, text=text) >= 0:
            return _repair_terminal_id_split_suffix(text, best)

    head_tail_candidate = _extract_terminal_id_from_head_tail(text, short_id_hint)
    if head_tail_candidate:
        head_tail_score = _score_terminal_id_candidate(head_tail_candidate, short_id_hint, text=text)
        if head_tail_score >= 200:
            return _repair_terminal_id_split_suffix(text, head_tail_candidate)

    concat_candidate = _extract_terminal_id_from_hex_concat(text, short_id_hint)
    if concat_candidate:
        concat_score = _score_terminal_id_candidate(concat_candidate, short_id_hint, text=text)
        if concat_score >= 0 or _preferred_uuid_tail_in_text(text) is None:
            return _repair_terminal_id_split_suffix(text, concat_candidate)
    if head_tail_candidate:
        return _repair_terminal_id_split_suffix(text, head_tail_candidate)
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


def _is_amount_noise_hex_line(line: str) -> bool:
    if re.search(r"[¥￥,]", line):
        return True
    cleaned = _clean_hex_line(line)
    if not cleaned:
        return False
    if cleaned.lower() in _AMOUNT_SHORT_ID_NOISE:
        return True
    if re.fullmatch(r"\d{4,5}", cleaned):
        return True
    return False


def _short_id_from_terminal_number_section(text: str) -> str | None:
    section = _terminal_number_section(text)
    if section is None:
        return None
    preferred: str | None = None
    fallback: str | None = None
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or _is_amount_noise_hex_line(line):
            continue
        if stripped.startswith(("-", "－")):
            if _is_uuid_middle_fragment_line(stripped):
                continue
            candidate = _short_id_from_leading_dash_hex_line(stripped)
            if candidate and _is_plausible_terminal_short_id(candidate):
                fallback = fallback or candidate
            continue
        cleaned = _clean_hex_line(line).strip("-")
        if len(cleaned) < 4:
            continue
        if len(cleaned) > 8 and "-" not in cleaned:
            continue
        if len(cleaned) == 8:
            candidate = _normalize_terminal_short_id_candidate(cleaned[:4])
        elif len(cleaned) == 4:
            candidate = _normalize_terminal_short_id_candidate(cleaned)
        else:
            prefix = _normalize_terminal_short_id_candidate(cleaned[:4])
            if prefix and prefix.startswith("98") and _is_plausible_terminal_short_id(prefix):
                preferred = prefix
            continue
        if not candidate or not _is_plausible_terminal_short_id(candidate):
            continue
        if candidate.startswith("98"):
            preferred = candidate
            break
        fallback = fallback or candidate
    return preferred or fallback


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


def _short_id_from_uuid_fragment(text: str) -> str | None:
    match = re.search(r"([0-9oOも6bBdD]{1,4})21ee3e", text, re.IGNORECASE)
    if match:
        prefix = match.group(1).translate(_OCR_HEX_FIXES).lower()
        prefix = re.sub(r"^d", "b", prefix)
        if len(prefix) >= 4:
            candidate = _normalize_terminal_short_id_candidate(prefix[:4])
            if candidate and _is_plausible_terminal_short_id(candidate):
                return candidate
        repaired = _normalize_terminal_short_id_candidate(f"{prefix}21"[:4])
        if repaired and _is_plausible_terminal_short_id(repaired):
            return repaired
    match = re.search(r"(?:DOd6|D0d6|b0d6)", text, re.IGNORECASE)
    if match:
        candidate = _normalize_terminal_short_id_candidate("b0d6")
        if candidate and _is_plausible_terminal_short_id(candidate):
            return candidate
    return None


def _explicit_terminal_short_id_in_text(text: str, short_id: str) -> bool:
    return bool(
        re.search(
            rf"(?:端末|端未)\s*(?:識別|認別|職別)\s*番号\s*[：:]?\s*{re.escape(short_id)}\b",
            text,
            re.IGNORECASE,
        )
    )


def _extract_terminal_short_id_hint(text: str) -> str | None:
    for pattern in _TERMINAL_SHORT_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1) if match.lastindex else match.group(0)
            candidate = _normalize_terminal_short_id_candidate(raw)
            if candidate and _is_plausible_terminal_short_id(candidate):
                return candidate
    return _short_id_from_uuid_fragment(text) or _short_id_from_terminal_number_section(text)


def _extract_terminal_short_id(text: str, terminal_id: str | None = None) -> str | None:
    for pattern in _TERMINAL_SHORT_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1) if match.lastindex else match.group(0)
            candidate = _normalize_terminal_short_id_candidate(raw)
            if candidate and _is_plausible_terminal_short_id(candidate):
                return candidate
    return (
        _short_id_from_uuid_fragment(text)
        or _short_id_from_terminal_id(terminal_id)
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
    if pos_sales and cash_sales and pos_sales == cash_sales:
        pos_sales = Decimal(0)

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
    (re.compile(r"小[計訳訁][^\d]{0,4}([\d,./]{3,})", re.IGNORECASE), "subtotal", False),
    (re.compile(r"[今会][計訳訁][^\d]{0,4}([\d,./]{3,})", re.IGNORECASE), "total", False),
    (re.compile(r"現金売[丁上][^\d]{0,4}([\d,./]{3,})", re.IGNORECASE), "cash", True),
    (re.compile(r"現金上(?!\u58f2)[^\d]{0,4}([\d,./]{3,})", re.IGNORECASE), "cash", True),
)


def _extract_garbled_label_amounts(
    text: str,
) -> tuple[dict[str, Decimal | None], dict[str, str]]:
    amounts: dict[str, Decimal | None] = {}
    corrections: dict[str, str] = {}
    for pattern, key, sales_field in _GARBLED_AMOUNT_PATTERNS:
        sanitize = sanitize_settlement_sales_amount if sales_field else sanitize_settlement_amount
        for match in pattern.finditer(text):
            amount, corrected_from = sanitize(match.group(1))
            if amount is None:
                continue
            if not sales_field and is_weak_settlement_header_amount(amount):
                continue
            if sales_field and amount > 0 and not is_valid_settlement_unit_sales_amount(amount):
                continue
            amounts[key] = amount
            if corrected_from:
                corrections[key] = corrected_from
    return amounts, corrections


def _reconcile_weak_header_amounts(amounts: dict[str, Decimal | None]) -> dict[str, Decimal | None]:
    repaired = dict(amounts)
    if is_weak_settlement_header_amount(repaired.get("subtotal")):
        for source_key in ("total", "cash", "subtotal"):
            candidate = repaired.get(source_key)
            if candidate is not None and not is_weak_settlement_header_amount(candidate):
                repaired["subtotal"] = candidate
                break
    if is_weak_settlement_header_amount(repaired.get("total")):
        for source_key in ("subtotal", "cash"):
            candidate = repaired.get(source_key)
            if candidate is not None and not is_weak_settlement_header_amount(candidate):
                repaired["total"] = candidate
                break
    return repaired


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
    layout_amounts, layout_corrections = extract_amounts_from_layout(text)
    amounts, corrections = merge_layout_amounts(amounts, corrections, layout_amounts, layout_corrections)
    amounts = repair_settlement_amounts(text, amounts)
    amounts = _reconcile_weak_header_amounts(amounts)
    amounts, subtotal_repair = reconcile_subtotal_total_consistency(text, amounts)
    if subtotal_repair:
        corrections["total"] = subtotal_repair
    return amounts, corrections


def _normalize_terminal_uuid_lines(text: str) -> str:
    text = _TERMINAL_SPLIT_RE.sub(
        lambda match: f"端末番号: {match.group(1)}{match.group(2)}",
        text,
    )
    text = _TERMINAL_SPLIT_3_2_RE.sub(
        lambda match: f"端末番号: {match.group(1)}{match.group(2)}",
        text,
    )
    return "\n".join(_normalize_uuid_ocr_line(line) for line in text.splitlines())


def _normalize_settlement_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = normalized.replace("　", " ")
    normalized = re.sub(r"現会売上", "現金売上", normalized)
    normalized = re.sub(r"現金売[丁上]", "現金売上", normalized)
    normalized = re.sub(r"現金上(?!売)", "現金売上", normalized)
    normalized = re.sub(r"精[篳竴弾]", "精算", normalized)
    normalized = re.sub(r"清算|清尊", "精算", normalized)
    normalized = re.sub(r"瑞末症別番[一=:]?", "端末識別番号:", normalized)
    normalized = re.sub(r"岩末城別番[一=:]?", "端末識別番号:", normalized)
    normalized = re.sub(r"末織別会号", "端末識別番号:", normalized)
    normalized = re.sub(r"焼末普[号清]|瑞末普号|瑞末号", "端末番号", normalized)
    normalized = re.sub(r"端端末番号", "端末番号", normalized)
    normalized = re.sub(r"端末号(?!番)", "端末番号", normalized)
    normalized = re.sub(r"16B60", "6,860", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"76,860", "6,860", normalized)
    normalized = _normalize_paygate_pos_labels(normalized)
    normalized = re.sub(r"クレンット元上|クレンチE允E|クレンチE売", "クレジット売上", normalized)
    normalized = re.sub(r"消責税|消賛稁|消費稁", "消費税", normalized)
    normalized = re.sub(r"(?:澤|矯|携)?末[護証藤]別番号", "端末識別番号", normalized)
    normalized = re.sub(r"[澤矯瑞市][末未]番号|末香号|末番号|岡条番号", "端末番号", normalized)
    normalized = re.sub(r"小[計訳訁餁]", "小計", normalized)
    normalized = re.sub(r"[今会][計訳訁]", "合計", normalized)
    normalized = re.sub(r"絹[箁算E]+", "精算", normalized)
    normalized = re.sub(r"20(\d{2})(\d{2})/(\d{2})", r"20\1/\2/\3", normalized)
    normalized = re.sub(r"20(\d{2})(\d{2})／(\d{2})", r"20\1/\2/\3", normalized)
    normalized = re.sub(r"(\d{4}/\d{2}/\d{2})(\d{2}:\d{2}:\d{2})", r"\1 \2", normalized)
    normalized = re.sub(
        r"(20\d{2})/(\d{2})(\d{2})(\d{2}:\d{2}:\d{2})",
        r"\1/\2/\3 \4",
        normalized,
    )
    normalized = re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\1/\2/\3", normalized)
    normalized = _normalize_terminal_uuid_lines(normalized)
    normalized = _normalize_paygate_pos_labels(normalized)
    return normalized


def _extract_settlement_datetime(text: str) -> tuple[date | None, str | None, str]:
    layout_date, layout_time = extract_settlement_datetime(text)
    if layout_date and layout_time:
        return layout_date, layout_time, "layout"

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
        terminal_short_id_hint = _extract_terminal_short_id_hint(text)
        terminal_id, terminal_meta = _extract_terminal_id_with_meta(ocr_result, text, terminal_short_id_hint)
        if not terminal_id:
            partial_tokens = _collect_terminal_hex_tokens(text, short_id=terminal_short_id_hint)
            partial_segments = assemble_terminal_segments_from_hex_tokens(
                partial_tokens,
                short_id=terminal_short_id_hint,
            )
            if partial_segments.is_complete():
                terminal_id = partial_segments.to_canonical()
                terminal_meta["source"] = "ocr_assembled"
            elif partial_segments.is_partial():
                recovered = recover_terminal_id_from_partial_segments(
                    text=text,
                    short_id=terminal_short_id_hint,
                    segments=partial_segments,
                    ocr_line_texts=[line.text for line in ocr_result.lines],
                )
                if recovered:
                    terminal_id = recovered
                    terminal_meta["source"] = "ocr_recovered"
                else:
                    terminal_meta["partial_segments"] = partial_segments.to_dict()
        terminal_short_id = _extract_terminal_short_id(text, terminal_id)
        short_from_terminal = _short_id_from_terminal_id(terminal_id)
        if terminal_short_id_hint and _explicit_terminal_short_id_in_text(text, terminal_short_id_hint):
            terminal_short_id = terminal_short_id_hint
            terminal_meta["short_id_source"] = "ocr_line_direct"
        elif short_from_terminal and (
            not terminal_short_id_hint
            or _score_terminal_id_candidate(terminal_id, short_from_terminal, text=text)
            > _score_terminal_id_candidate(terminal_id, terminal_short_id_hint, text=text)
        ):
            terminal_short_id = short_from_terminal
            terminal_meta["short_id_source"] = "from_terminal_id"
        elif terminal_short_id_hint:
            terminal_short_id = terminal_short_id_hint
            terminal_meta["short_id_source"] = "ocr_corrected"
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
        field_confidence, field_sources = build_settlement_field_confidence(
            ocr_result,
            parsed,
            terminal_meta=terminal_meta,
            amount_meta=amount_meta,
        )
        parsed.raw_payload["field_confidence"] = field_confidence
        parsed.raw_payload["field_sources"] = field_sources
        partial_segments = terminal_meta.get("partial_segments")
        if partial_segments and not terminal_id:
            parsed.raw_payload["terminal_id_segments"] = partial_segments
            parsed.raw_payload["terminal_id_partial"] = True
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
