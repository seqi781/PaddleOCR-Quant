from pathlib import Path

from paddleocr_quant.ingestion import build_document_metadata
from paddleocr_quant.models import DocumentMetadataIn
from paddleocr_quant.parser import ParserRegistry
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
