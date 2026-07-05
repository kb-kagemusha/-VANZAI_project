"""Settlement receipt terminal_id (端末番号) format rules.

- 英数字のみ
- 8桁-4桁-4桁-4桁-12桁（ハイフン区切り）
- アルファベットは小文字 a～f のみ（16進）
- 数字は 0～9 のみ

端末識別番号 (terminal_short_id):
- 必ず4桁（16進小文字 0-9a-f）
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_SETTLEMENT_TERMINAL_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
_SETTLEMENT_TERMINAL_SHORT_ID_RE = re.compile(r"^[0-9a-f]{4}$")
_REGISTRATION_SEGMENT_RE = re.compile(r"^\d{4}$")
_OCR_SHORT_ID_FIXES = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "Ｏ": "0",
        "ｏ": "0",
        "Ｉ": "1",
        "ｌ": "1",
        "l": "1",
        "G": "0",
        "g": "0",
        "\u0111": "d",
        "\u0110": "d",
        "\u3058": "b",  # じ
        "\u3082": "b",  # も
        "\u65e5": "b",  # 日（UUID断片の 475日→475b 向け。日付は別途正規化）
    }
)


def _repair_all_digit_short_id(value: str) -> str | None:
    """OCR が e を 0 と誤読した 4 桁数字（例: 8402 → 84e2）を復元する。"""
    if not re.fullmatch(r"\d{4}", value):
        return None
    for index, char in enumerate(value):
        if char != "0":
            continue
        trial = f"{value[:index]}e{value[index + 1:]}"
        if _SETTLEMENT_TERMINAL_SHORT_ID_RE.fullmatch(trial):
            return trial
    return None


def _repair_ob21_digit_short_id(value: str) -> str | None:
    """OCR が b を 6 と誤読した 4 桁（例: 0621 → 0b21）を復元する。"""
    if not re.fullmatch(r"0\d{3}", value):
        return None
    trial = f"0b{value[2:]}"
    if _SETTLEMENT_TERMINAL_SHORT_ID_RE.fullmatch(trial):
        return trial
    return None


def _fold_ocr_accents(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    return "".join(char for char in folded if not unicodedata.combining(char))


def format_terminal_id_from_hex32(hex_only: str) -> str:
    return (
        f"{hex_only[:8]}-{hex_only[8:12]}-{hex_only[12:16]}-"
        f"{hex_only[16:20]}-{hex_only[20:32]}"
    )


def is_valid_settlement_terminal_id(value: str | None) -> bool:
    if not value:
        return False
    return _SETTLEMENT_TERMINAL_ID_RE.fullmatch(value.strip().lower()) is not None


def normalize_settlement_terminal_id(value: str | None) -> str | None:
    """Return canonical terminal_id or None if the value does not match the rules."""
    if not value:
        return None
    cleaned = _fold_ocr_accents(value.strip().lower()).translate(_OCR_SHORT_ID_FIXES).replace(" ", "")
    if _SETTLEMENT_TERMINAL_ID_RE.fullmatch(cleaned):
        return cleaned
    hex_only = re.sub(r"[^0-9a-f]", "", cleaned)
    if len(hex_only) == 32 and _HEX32_RE.fullmatch(hex_only):
        return format_terminal_id_from_hex32(hex_only)
    return None


def _repair_98f0_short_id_candidate(value: str) -> str | None:
    """端末識別番号 98f0 の OCR 誤読（981e / 9810 / 980 等）を復元。"""
    if not value:
        return None
    lowered = value.lower()
    if lowered in {"981e", "9810", "9800", "98fe", "98ie", "98o0", "980e"}:
        return "98f0"
    if re.fullmatch(r"98[01o][0oef]", lowered):
        return "98f0"
    if lowered == "980":
        return "98f0"
    return None


def normalize_settlement_terminal_short_id(
    value: str | None,
    *,
    from_ocr: bool = False,
) -> str | None:
    """端末識別番号を正規化する。必ず4桁16進（0-9a-f）。"""
    if not value:
        return None
    translated = _fold_ocr_accents(value.strip()).translate(_OCR_SHORT_ID_FIXES)
    candidate = re.sub(r"[^0-9a-fA-F]", "", translated).lower()
    if from_ocr:
        if len(candidate) < 4:
            if len(candidate) == 3 and candidate.startswith("98"):
                candidate = "98f0"
            else:
                return None
        if len(candidate) > 4:
            candidate = candidate[:4]
        repaired_98f0 = _repair_98f0_short_id_candidate(candidate)
        if repaired_98f0:
            candidate = repaired_98f0
        if candidate.isdigit():
            repaired = _repair_ob21_digit_short_id(candidate) or _repair_all_digit_short_id(candidate)
            if repaired:
                candidate = repaired
    elif len(candidate) != 4:
        return None
    if _REGISTRATION_SEGMENT_RE.fullmatch(candidate):
        return None
    if candidate.isdigit():
        return None
    if _SETTLEMENT_TERMINAL_SHORT_ID_RE.fullmatch(candidate):
        return candidate
    return None


def is_valid_settlement_terminal_short_id(value: str | None) -> bool:
    return normalize_settlement_terminal_short_id(value) is not None


class TerminalIdSegments:
  """UUID segments for settlement terminal_id (8-4-4-4-12)."""

  __slots__ = ("eight", "four_1", "four_2", "four_3", "twelve")

  def __init__(
      self,
      *,
      eight: str | None = None,
      four_1: str | None = None,
      four_2: str | None = None,
      four_3: str | None = None,
      twelve: str | None = None,
  ) -> None:
      self.eight = eight
      self.four_1 = four_1
      self.four_2 = four_2
      self.four_3 = four_3
      self.twelve = twelve

  def is_complete(self) -> bool:
      return all((self.eight, self.four_1, self.four_2, self.four_3, self.twelve))

  def is_partial(self) -> bool:
      return any((self.eight, self.four_1, self.four_2, self.four_3, self.twelve)) and not self.is_complete()

  def to_canonical(self) -> str | None:
      if not self.is_complete():
          return None
      return f"{self.eight}-{self.four_1}-{self.four_2}-{self.four_3}-{self.twelve}"

  def to_dict(self) -> dict[str, str]:
      payload: dict[str, str] = {}
      if self.eight:
          payload["eight"] = self.eight
      if self.four_1:
          payload["four_1"] = self.four_1
      if self.four_2:
          payload["four_2"] = self.four_2
      if self.four_3:
          payload["four_3"] = self.four_3
      if self.twelve:
          payload["twelve"] = self.twelve
      return payload

  @classmethod
  def from_dict(cls, payload: dict[str, str] | None) -> "TerminalIdSegments":
      if not payload:
          return cls()
      return cls(
          eight=payload.get("eight"),
          four_1=payload.get("four_1"),
          four_2=payload.get("four_2"),
          four_3=payload.get("four_3"),
          twelve=payload.get("twelve"),
      )


def _is_short_id_noise_token(token: str, short_id: str | None) -> bool:
    if not short_id or len(token) != 4:
        return False
    if token == short_id:
        return True
    repaired = normalize_settlement_terminal_short_id(token, from_ocr=True)
    return repaired == short_id and token != short_id


def assemble_terminal_segments_from_hex_tokens(
    tokens: list[str],
    *,
    short_id: str | None = None,
) -> TerminalIdSegments:
    """Pick best-available UUID segments from OCR hex tokens."""
    eight_chars = [
        token
        for token in tokens
        if len(token) == 8 and (not short_id or token.startswith(short_id))
    ]
    four_chars = [
        token
        for token in tokens
        if len(token) == 4 and not _is_short_id_noise_token(token, short_id)
    ]
    twelve_chars = [token for token in tokens if len(token) == 12 and not token.startswith("af4c")]
    if not twelve_chars:
        twelve_chars = [token for token in tokens if len(token) == 12]

    ordered_fours: list[str] = []
    for token in tokens:
        if token in eight_chars:
            continue
        if len(token) == 4 and token not in ordered_fours and not _is_short_id_noise_token(token, short_id):
            ordered_fours.append(token)
        if len(ordered_fours) == 3:
            break
    if len(ordered_fours) < 3:
        ordered_fours = []
        for token in four_chars:
            if eight_chars and token == eight_chars[0][:4]:
                continue
            if token not in ordered_fours:
                ordered_fours.append(token)
            if len(ordered_fours) == 3:
                break

    return TerminalIdSegments(
        eight=eight_chars[0] if eight_chars else None,
        four_1=ordered_fours[0] if len(ordered_fours) > 0 else None,
        four_2=ordered_fours[1] if len(ordered_fours) > 1 else None,
        four_3=ordered_fours[2] if len(ordered_fours) > 2 else None,
        twelve=twelve_chars[-1] if twelve_chars else None,
    )


def format_terminal_id_display_lines(value: str | None) -> tuple[str, str] | None:
    if not value or not is_valid_settlement_terminal_id(value):
        return None
    parts = value.split("-")
    if len(parts) != 5:
        return None
    return f"{parts[0]}-{parts[1]}-{parts[2]}-", f"{parts[3]}-{parts[4]}"


def format_terminal_segments_display_lines(segments: TerminalIdSegments) -> tuple[str, str]:
    line1_parts = [segments.eight, segments.four_1, segments.four_2]
    line1_joined = "-".join(part for part in line1_parts if part)
    line1 = f"{line1_joined}-" if line1_joined else "—"
    line2_parts = [segments.four_3, segments.twelve]
    line2 = "-".join(part for part in line2_parts if part) or "—"
    return line1, line2


def terminal_id_is_partial_from_payload(raw_payload: dict[str, Any] | None) -> bool:
    if not raw_payload:
        return False
    if raw_payload.get("terminal_id_partial"):
        return True
    segments = TerminalIdSegments.from_dict(raw_payload.get("terminal_id_segments"))
    return segments.is_partial()


def terminal_id_segments_from_payload(raw_payload: dict[str, Any] | None) -> TerminalIdSegments:
    return TerminalIdSegments.from_dict((raw_payload or {}).get("terminal_id_segments"))
