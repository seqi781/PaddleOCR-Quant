from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from paddleocr_quant.bootstrap import build_container
from paddleocr_quant.ingestion import build_document_metadata
from paddleocr_quant.models import CompanyMetricRecord, DocumentMetadataIn, FieldExtractionResult, QARequest
from paddleocr_quant.normalization import normalize_fields
from paddleocr_quant.retrieval import build_grounded_answer, query_from_question
from paddleocr_quant.scoring import score_company
from paddleocr_quant.seeds import seed_repository
from paddleocr_quant.settings import get_settings

app = typer.Typer(help="PaddleOCR-Quant local MVP CLI.")


@app.command("seed")
def seed_command() -> None:
    container = build_container(get_settings())
    records = seed_repository(container.repo, container.fixtures_dir)
    typer.echo(f"Seeded {len(records)} company metric records.")


@app.command("score")
def score_command(company_code: str, fiscal_year: int) -> None:
    container = build_container(get_settings())
    record = container.repo.get_company_metric(company_code, fiscal_year)
    if not record:
        raise typer.BadParameter(f"No metric found for {company_code} in {fiscal_year}")
    typer.echo(json.dumps(score_company(record).model_dump(), ensure_ascii=False, indent=2))


@app.command("ingest")
def ingest_command(
    path: Path,
    company_code: str,
    company_name: str,
    fiscal_year: int,
    market: str = "CN_A",
    report_type: str = "annual_report",
    language: str = "zh-CN",
) -> None:
    container = build_container(get_settings())
    payload = DocumentMetadataIn(
        company_code=company_code,
        company_name=company_name,
        market=market,
        fiscal_year=fiscal_year,
        report_type=report_type,
        language=language,
        source_path=str(path),
        source_fixture=None,
    )
    try:
        metadata = build_document_metadata(payload, container.object_store)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    container.repo.insert_document(metadata)
    container.object_store.put_json(f"documents/{metadata.document_id}.json", metadata.model_dump(mode="json"))
    typer.echo(json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("parse")
def parse_command(document_id: str) -> None:
    container = build_container(get_settings())
    metadata = container.repo.get_document(document_id)
    if not metadata:
        raise typer.BadParameter(f"Document not found: {document_id}")
    result = container.parser_registry.parse(metadata)
    container.repo.upsert_parse_result(result)
    container.repo.update_document_parse_status(document_id, result.parser_name, datetime.utcnow().isoformat())
    container.object_store.put_json(f"parsed/{document_id}.json", result.model_dump(mode="json"))
    normalized = normalize_fields(result.extracted_fields)
    container.repo.upsert_company_metric(
        CompanyMetricRecord(
            company_code=metadata.company_code,
            company_name=metadata.company_name,
            market=metadata.market,
            fiscal_year=metadata.fiscal_year,
            currency="USD" if metadata.market == "US" else "CNY",
            normalized_fields=normalized,
        )
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("inspect")
def inspect_command(document_id: str) -> None:
    container = build_container(get_settings())
    metadata = container.repo.get_document(document_id)
    if not metadata:
        raise typer.BadParameter(f"Document not found: {document_id}")
    inspection = container.parser_registry.inspect(metadata)
    typer.echo(json.dumps(inspection.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("parse-ocr")
def parse_ocr_command(document_id: str) -> None:
    container = build_container(get_settings())
    metadata = container.repo.get_document(document_id)
    if not metadata:
        raise typer.BadParameter(f"Document not found: {document_id}")
    result = container.parser_registry.parse_ocr(metadata)
    container.repo.upsert_parse_result(result)
    container.repo.update_document_parse_status(document_id, result.parser_name, datetime.utcnow().isoformat())
    container.object_store.put_json(f"parsed/{document_id}.json", result.model_dump(mode="json"))
    normalized = normalize_fields(result.extracted_fields)
    container.repo.upsert_company_metric(
        CompanyMetricRecord(
            company_code=metadata.company_code,
            company_name=metadata.company_name,
            market=metadata.market,
            fiscal_year=metadata.fiscal_year,
            currency="USD" if metadata.market == "US" else "CNY",
            normalized_fields=normalized,
        )
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("extract-fields")
def extract_fields_command(
    path: Path,
    market: str = "CN_A",
    language: str = "zh-CN",
) -> None:
    container = build_container(get_settings())
    payload = DocumentMetadataIn(
        company_code="EXTRACT",
        company_name="Extraction Only",
        market=market,
        fiscal_year=datetime.utcnow().year,
        report_type="extraction_only",
        language=language,
        source_path=str(path),
        source_fixture=None,
    )
    try:
        metadata = build_document_metadata(payload, container.object_store)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    result = container.parser_registry.parse(metadata)
    response = FieldExtractionResult(
        document_id=metadata.document_id,
        source=str(path),
        extracted_fields=result.extracted_fields,
        warnings=result.warnings,
        metadata={
            "parser_name": result.parser_name,
            "strategy": result.strategy,
            "parse_metadata": result.metadata,
        },
    )
    typer.echo(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("search")
def search_command(document_id: str, query: str, limit: int = 5) -> None:
    container = build_container(get_settings())
    result = container.repo.search_chunks(document_id=document_id, query=query, limit=limit)
    typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("ask")
def ask_command(document_id: str, question: str, top_k: int = 3) -> None:
    container = build_container(get_settings())
    payload = QARequest(question=question, top_k=top_k)
    search_result = container.repo.search_chunks(
        document_id=document_id,
        query=query_from_question(payload.question),
        limit=payload.top_k,
    )
    response = build_grounded_answer(document_id=document_id, question=payload.question, search_result=search_result)
    typer.echo(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("sample-filings")
def sample_filings_command(market: str, ticker: str = "") -> None:
    container = build_container(get_settings())
    if market not in {"CN_A", "HK", "US"}:
        raise typer.BadParameter(f"Unsupported market: {market}")
    filings = container.filing_sources.list_sample_filings(market=market, ticker=ticker)
    typer.echo(json.dumps([item.model_dump() for item in filings], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
