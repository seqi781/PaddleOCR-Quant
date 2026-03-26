from pathlib import Path

from paddleocr_quant.ingestion import build_document_metadata
from paddleocr_quant.models import DocumentMetadataIn
from paddleocr_quant.parser import ParserRegistry
from paddleocr_quant.pdf import PDFInspectionResult
from paddleocr_quant.storage import LocalObjectStore


def test_text_parser_extracts_aliases_from_markdown(tmp_path: Path) -> None:
    source = tmp_path / "sample.md"
    source.write_text(
        "# 2025 Annual Report\n\nRevenue: 1,250\nNet Profit 320\nGross Margin 44.5%\n",
        encoding="utf-8",
    )
    object_store = LocalObjectStore(tmp_path / "object_store")
    metadata = build_document_metadata(
        DocumentMetadataIn(
            company_code="AAPL",
            company_name="Apple",
            market="US",
            fiscal_year=2025,
            report_type="annual_report",
            language="en-US",
            source_path=str(source),
            source_fixture=None,
        ),
        object_store,
    )
    parser = ParserRegistry(fixtures_dir=Path("fixtures")).select(metadata)
    result = parser.parse(metadata)

    names = {field.name.lower() for field in result.extracted_fields}
    assert result.parser_name == "text-heuristic"
    assert "revenue" in names
    assert "net profit" in names
    assert "gross margin" in names
    assert result.chunks


def test_html_parser_strips_tags_and_extracts_text(tmp_path: Path) -> None:
    source = tmp_path / "sample.html"
    source.write_text(
        "<html><body><h1>Revenue 980</h1><p>Operating cash flow: 210</p></body></html>",
        encoding="utf-8",
    )
    object_store = LocalObjectStore(tmp_path / "object_store")
    metadata = build_document_metadata(
        DocumentMetadataIn(
            company_code="0700.HK",
            company_name="Tencent",
            market="HK",
            fiscal_year=2025,
            report_type="annual_report",
            language="en-US",
            source_path=str(source),
            source_fixture=None,
        ),
        object_store,
    )
    parser = ParserRegistry(fixtures_dir=Path("fixtures")).select(metadata)
    result = parser.parse(metadata)

    assert "Revenue 980" in result.extracted_text
    assert "Operating cash flow: 210" in result.extracted_text
    assert any(field.name.lower() == "operating cash flow" for field in result.extracted_fields)


def test_pdf_strategy_detection_prefers_text_when_extractable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4 test")
    object_store = LocalObjectStore(tmp_path / "object_store")
    metadata = build_document_metadata(
        DocumentMetadataIn(
            company_code="AAPL",
            company_name="Apple",
            market="US",
            fiscal_year=2025,
            source_path=str(source),
            source_fixture=None,
        ),
        object_store,
    )

    monkeypatch.setattr(
        "paddleocr_quant.parser.inspect_pdf_text",
        lambda _path: PDFInspectionResult(text_extractable=True, page_count=2, extracted_text="Revenue 1000"),
    )

    inspection = ParserRegistry(fixtures_dir=Path("fixtures"), object_store_root=object_store.root).inspect(metadata)

    assert inspection.recommended_strategy == "text"
    assert inspection.text_extractable is True
    assert inspection.page_count == 2


def test_pdf_ocr_fallback_returns_warnings_without_crashing(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "scanned.pdf"
    source.write_bytes(b"%PDF-1.4 scanned")
    object_store = LocalObjectStore(tmp_path / "object_store")
    metadata = build_document_metadata(
        DocumentMetadataIn(
            company_code="600519.SH",
            company_name="Moutai",
            market="CN_A",
            fiscal_year=2025,
            source_path=str(source),
            source_fixture=None,
        ),
        object_store,
    )

    monkeypatch.setattr(
        "paddleocr_quant.parser.inspect_pdf_text",
        lambda _path: PDFInspectionResult(text_extractable=False, page_count=2),
    )

    result = ParserRegistry(fixtures_dir=Path("fixtures"), object_store_root=object_store.root).parse(metadata)

    assert result.strategy == "ocr"
    assert result.page_results
    assert any(page.status == "unavailable" for page in result.page_results)
    assert any("PaddleOCR is not installed" in warning for warning in result.warnings)
