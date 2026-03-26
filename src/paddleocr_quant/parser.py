from __future__ import annotations

import html
import json
import re
from abc import ABC, abstractmethod
from html.parser import HTMLParser
from pathlib import Path

from paddleocr_quant.normalization import FIELD_ALIASES
from paddleocr_quant.models import DocumentMetadata, ParseResult, ParsedField, TextChunk


class DocumentParser(ABC):
    name: str

    @abstractmethod
    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        raise NotImplementedError


class MockPaddleOCRParser(DocumentParser):
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
            extracted_text="\n\n".join(payload["chunks"]),
            extracted_fields=extracted_fields,
            chunks=chunks,
        )


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def _split_text(text: str, chunk_size: int = 500) -> list[str]:
    units = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    for unit in units or [text.strip()]:
        if not unit:
            continue
        if len(unit) <= chunk_size:
            chunks.append(unit)
            continue
        for start in range(0, len(unit), chunk_size):
            snippet = unit[start : start + chunk_size].strip()
            if snippet:
                chunks.append(snippet)
    return chunks


def _parse_numeric_token(token: str) -> float:
    cleaned = token.replace(",", "").replace("%", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    return float(cleaned)


def _extract_financial_aliases(text: str) -> list[ParsedField]:
    fields: list[ParsedField] = []
    seen: set[tuple[str, float]] = set()
    aliases = sorted(FIELD_ALIASES.keys(), key=len, reverse=True)
    for line in text.splitlines():
        normalized_line = html.unescape(line).strip()
        if not normalized_line:
            continue
        for alias in aliases:
            match = re.search(
                rf"(?i){re.escape(alias)}[\s:：\-]*([\(]?-?\d[\d,]*(?:\.\d+)?\)?%?)",
                normalized_line,
            )
            if not match:
                continue
            value = _parse_numeric_token(match.group(1))
            key = (alias.lower(), value)
            if key in seen:
                continue
            seen.add(key)
            unit = "%"
            if "%" not in match.group(1):
                unit = "USD" if "$" in normalized_line or "usd" in normalized_line.lower() else "CNY"
            fields.append(
                ParsedField(
                    name=alias,
                    value=value,
                    unit=unit,
                    source_text=normalized_line,
                )
            )
    return fields


class TextDocumentParser(DocumentParser):
    name = "text-heuristic"

    def _read_text(self, metadata: DocumentMetadata) -> str:
        assert metadata.source_path
        path = Path(metadata.source_path)
        suffix = path.suffix.lower()
        raw = path.read_text(encoding="utf-8")
        if suffix == ".html":
            extractor = _HTMLTextExtractor()
            extractor.feed(raw)
            return extractor.text()
        return raw

    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        text = self._read_text(metadata)
        chunks = [
            TextChunk(
                document_id=metadata.document_id,
                seq=index,
                text=chunk,
                metadata={"parser": self.name, "extension": metadata.detected_extension},
            )
            for index, chunk in enumerate(_split_text(text), start=1)
        ]
        return ParseResult(
            document_id=metadata.document_id,
            parser_name=self.name,
            extracted_text=text,
            extracted_fields=_extract_financial_aliases(text),
            chunks=chunks,
        )


class PDFDocumentParser(DocumentParser):
    name = "pdf-fallback"

    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        assert metadata.source_path
        warnings: list[str] = []
        extracted_text = ""
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(metadata.source_path)
            extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except ImportError:
            warnings.append("PDF parsing requires optional dependency `pypdf`; returning placeholder text.")
        except Exception as exc:
            warnings.append(f"PDF parsing failed: {exc}")

        if not extracted_text:
            extracted_text = (
                f"PDF document available at {metadata.source_path}. "
                "Text extraction is unavailable in this lightweight environment."
            )

        chunks = [
            TextChunk(
                document_id=metadata.document_id,
                seq=index,
                text=chunk,
                metadata={"parser": self.name, "extension": ".pdf"},
            )
            for index, chunk in enumerate(_split_text(extracted_text), start=1)
        ]
        return ParseResult(
            document_id=metadata.document_id,
            parser_name=self.name,
            extracted_text=extracted_text,
            extracted_fields=_extract_financial_aliases(extracted_text),
            chunks=chunks,
            warnings=warnings,
        )


class ParserRegistry:
    def __init__(self, fixtures_dir: Path) -> None:
        self.mock_parser = MockPaddleOCRParser(fixtures_dir)
        self.text_parser = TextDocumentParser()
        self.pdf_parser = PDFDocumentParser()

    def select(self, metadata: DocumentMetadata) -> DocumentParser:
        if metadata.parser_hint == self.mock_parser.name:
            return self.mock_parser
        extension = (metadata.detected_extension or "").lower()
        if metadata.source_type == "fixture":
            return self.mock_parser
        if extension in {".txt", ".md", ".markdown", ".html", ".htm"}:
            return self.text_parser
        if extension == ".pdf":
            return self.pdf_parser
        return self.text_parser
