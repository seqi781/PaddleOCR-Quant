from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from paddleocr_quant.models import DocumentMetadata, ParseResult, ParsedField, TextChunk


class DocumentParser(ABC):
    name: str

    @abstractmethod
    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        raise NotImplementedError


class MockPaddleOCRParser:
    name = "mock-paddleocr"

    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir

    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        fixture_path = self.fixtures_dir / "mock_ocr" / metadata.source_fixture
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        extracted_fields = [ParsedField.model_validate(item) for item in payload["extracted_fields"]]
        chunks = [
            TextChunk(
                document_id=metadata.document_id,
                seq=index,
                text=text,
                metadata={"parser": self.name, "fixture": metadata.source_fixture},
            )
            for index, text in enumerate(payload["chunks"], start=1)
        ]
        return ParseResult(
            document_id=metadata.document_id,
            parser_name=self.name,
            extracted_fields=extracted_fields,
            chunks=chunks,
        )
