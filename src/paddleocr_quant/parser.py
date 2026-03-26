from __future__ import annotations

import html
import json
import re
from abc import ABC, abstractmethod
from html.parser import HTMLParser
from pathlib import Path

from paddleocr_quant.models import (
    DocumentInspection,
    DocumentMetadata,
    OCRPageResult,
    ParseResult,
    ParsedField,
    TextChunk,
)
from paddleocr_quant.normalization import FIELD_ALIASES
from paddleocr_quant.ocr import OCRAdapter, PaddleOCRAdapter
from paddleocr_quant.pdf import PreparedPageImage, inspect_pdf_text, prepare_pdf_page_images


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
            strategy="mock",
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
            strategy="text",
            extracted_text=text,
            extracted_fields=_extract_financial_aliases(text),
            chunks=chunks,
        )


class PDFDocumentParser(DocumentParser):
    name = "pdf-document"

    def __init__(self, object_store_root: Path, ocr_adapter: OCRAdapter | None = None) -> None:
        self.object_store_root = object_store_root
        self.ocr_adapter = ocr_adapter or PaddleOCRAdapter()

    def inspect(self, metadata: DocumentMetadata) -> DocumentInspection:
        assert metadata.source_path
        inspection = inspect_pdf_text(metadata.source_path)
        recommended_strategy = "ocr"
        if inspection.text_extractable:
            recommended_strategy = "text"
        return DocumentInspection(
            document_id=metadata.document_id,
            parser_name=self.name,
            recommended_strategy=recommended_strategy,
            detected_extension=metadata.detected_extension,
            source_type=metadata.source_type,
            text_extractable=inspection.text_extractable,
            page_count=inspection.page_count,
            warnings=inspection.warnings,
            metadata={"ocr_adapter": self.ocr_adapter.name},
        )

    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        inspection = self.inspect(metadata)
        if inspection.recommended_strategy == "text":
            return self.parse_via_text(metadata, inspection)
        return self.parse_via_ocr(metadata, inspection)

    def parse_via_text(
        self,
        metadata: DocumentMetadata,
        inspection: DocumentInspection | None = None,
    ) -> ParseResult:
        assert metadata.source_path
        pdf_inspection = inspect_pdf_text(metadata.source_path)
        extracted_text = pdf_inspection.extracted_text
        warnings = [*(inspection.warnings if inspection else []), *pdf_inspection.warnings]
        if not extracted_text:
            warnings.append("PDF text extraction produced no text; OCR is recommended for this document.")
            extracted_text = (
                f"PDF document available at {metadata.source_path}. "
                "No extractable text was found by the current lightweight parser."
            )
        chunks = [
            TextChunk(
                document_id=metadata.document_id,
                seq=index,
                text=chunk,
                metadata={"parser": self.name, "extension": ".pdf", "strategy": "text"},
            )
            for index, chunk in enumerate(_split_text(extracted_text), start=1)
        ]
        return ParseResult(
            document_id=metadata.document_id,
            parser_name=self.name,
            strategy="text",
            extracted_text=extracted_text,
            extracted_fields=_extract_financial_aliases(extracted_text),
            chunks=chunks,
            warnings=_dedupe_preserve_order(warnings),
        )

    def parse_via_ocr(
        self,
        metadata: DocumentMetadata,
        inspection: DocumentInspection | None = None,
    ) -> ParseResult:
        assert metadata.source_path
        prep = prepare_pdf_page_images(
            metadata.source_path,
            self.object_store_root / "prepared_pages" / metadata.document_id,
            page_count_hint=inspection.page_count if inspection else None,
        )
        ocr_result = self.ocr_adapter.run(prep.page_images)
        warnings = [
            *(inspection.warnings if inspection else []),
            *prep.warnings,
            *ocr_result.warnings,
        ]
        extracted_text = ocr_result.extracted_text.strip()
        if not extracted_text:
            extracted_text = (
                f"PDF document available at {metadata.source_path}. "
                "OCR text is unavailable in the current environment."
            )
        chunks = [
            TextChunk(
                document_id=metadata.document_id,
                seq=index,
                text=chunk,
                metadata={
                    "parser": self.name,
                    "extension": ".pdf",
                    "strategy": "ocr",
                    "ocr_adapter": self.ocr_adapter.name,
                },
            )
            for index, chunk in enumerate(_split_text(extracted_text), start=1)
        ]
        page_results = ocr_result.page_results or _placeholder_page_results(prep.page_images, self.ocr_adapter.name)
        return ParseResult(
            document_id=metadata.document_id,
            parser_name=self.name,
            strategy="ocr",
            extracted_text=extracted_text,
            extracted_fields=_extract_financial_aliases(extracted_text),
            chunks=chunks,
            page_results=page_results,
            warnings=_dedupe_preserve_order(warnings),
        )


def _placeholder_page_results(page_images: list[PreparedPageImage], adapter_name: str) -> list[OCRPageResult]:
    results: list[OCRPageResult] = []
    for page in page_images:
        results.append(
            OCRPageResult(
                page_number=page.page_number,
                status="warning",
                image_path=page.image_path,
                warnings=page.warnings,
                metadata={"adapter": adapter_name, **page.metadata},
            )
        )
    return results


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


class ParserRegistry:
    def __init__(self, fixtures_dir: Path, object_store_root: Path | None = None) -> None:
        self.mock_parser = MockPaddleOCRParser(fixtures_dir)
        self.text_parser = TextDocumentParser()
        self.pdf_parser = PDFDocumentParser(object_store_root=object_store_root or Path("data/object_store"))

    def inspect(self, metadata: DocumentMetadata) -> DocumentInspection:
        if metadata.parser_hint == self.mock_parser.name or metadata.source_type == "fixture":
            return DocumentInspection(
                document_id=metadata.document_id,
                parser_name=self.mock_parser.name,
                recommended_strategy="mock",
                detected_extension=metadata.detected_extension,
                source_type=metadata.source_type,
                warnings=[],
                metadata={"reason": "fixture or mock parser hint"},
            )

        extension = (metadata.detected_extension or "").lower()
        if extension in {".txt", ".md", ".markdown", ".html", ".htm"}:
            return DocumentInspection(
                document_id=metadata.document_id,
                parser_name=self.text_parser.name,
                recommended_strategy="text",
                detected_extension=metadata.detected_extension,
                source_type=metadata.source_type,
            )
        if extension == ".pdf":
            return self.pdf_parser.inspect(metadata)
        return DocumentInspection(
            document_id=metadata.document_id,
            parser_name=self.text_parser.name,
            recommended_strategy="text",
            detected_extension=metadata.detected_extension,
            source_type=metadata.source_type,
            warnings=["Unknown extension; defaulting to text parser."],
        )

    def select(self, metadata: DocumentMetadata) -> DocumentParser:
        inspection = self.inspect(metadata)
        if inspection.recommended_strategy == "mock":
            return self.mock_parser
        if metadata.detected_extension == ".pdf":
            return self.pdf_parser
        return self.text_parser

    def parse(self, metadata: DocumentMetadata) -> ParseResult:
        inspection = self.inspect(metadata)
        if inspection.recommended_strategy == "mock":
            return self.mock_parser.parse(metadata)
        if metadata.detected_extension == ".pdf":
            return self.pdf_parser.parse(metadata)
        return self.text_parser.parse(metadata)

    def parse_ocr(self, metadata: DocumentMetadata) -> ParseResult:
        inspection = self.inspect(metadata)
        if metadata.detected_extension == ".pdf":
            return self.pdf_parser.parse_via_ocr(metadata, inspection)
        warning = "Explicit OCR parse is only implemented for PDF documents; falling back to selected parser."
        result = self.parse(metadata)
        result.warnings = _dedupe_preserve_order([warning, *result.warnings])
        return result
