"""Parser registry for extensible source types."""
from __future__ import annotations

from src.services.ocr.parsers.base import BaseOcrParser
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.parsers.paygate_settlement import PaygateSettlementParser

PARSERS: dict[str, BaseOcrParser] = {
    PaygateScreenshotParser.source_type: PaygateScreenshotParser(),
    PaygateSettlementParser.source_type: PaygateSettlementParser(),
}

VALID_SOURCE_TYPES = frozenset(PARSERS.keys())


def get_parser(source_type: str) -> BaseOcrParser:
    parser = PARSERS.get(source_type)
    if parser is None:
        raise ValueError(f"Unsupported source_type: {source_type}")
    return parser
