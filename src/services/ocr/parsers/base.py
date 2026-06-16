"""Base parser interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.services.ocr.models import OcrEngineResult, ParsedOcrRow


class BaseOcrParser(ABC):
    source_type: str

    @abstractmethod
    def parse(self, ocr_result: OcrEngineResult) -> list[ParsedOcrRow]:
        raise NotImplementedError
