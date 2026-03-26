from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException

from paddleocr_quant.bootstrap import Container, build_container
from paddleocr_quant.ingestion import build_document_metadata
from paddleocr_quant.models import (
    CompareRequest,
    CompareResult,
    CompanyMetricRecord,
    DocumentMetadata,
    DocumentMetadataIn,
    ParseResult,
    QARequest,
    QAResponse,
    SampleFiling,
    SearchResult,
    ScoreBreakdown,
    ScoreRequest,
)
from paddleocr_quant.normalization import normalize_fields
from paddleocr_quant.retrieval import build_grounded_answer, query_from_question
from paddleocr_quant.scoring import score_company
from paddleocr_quant.seeds import seed_repository
from paddleocr_quant.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    container = build_container(resolved_settings)

    app = FastAPI(title=resolved_settings.app_name, version="0.1.0")
    app.state.container = container

    @app.on_event("startup")
    def startup() -> None:
        seed_repository(container.repo, container.fixtures_dir)

    def get_container() -> Container:
        return app.state.container

    @app.get("/health")
    def health(dep: Container = Depends(get_container)) -> dict:
        return {
            "status": "ok",
            "app": dep.settings.app_name,
            "env": dep.settings.app_env,
        }

    @app.post("/documents", response_model=DocumentMetadata)
    def ingest_document(
        payload: DocumentMetadataIn,
        dep: Container = Depends(get_container),
    ) -> DocumentMetadata:
        try:
            metadata = build_document_metadata(payload, dep.object_store)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        dep.repo.insert_document(metadata)
        dep.object_store.put_json(
            f"documents/{metadata.document_id}.json",
            metadata.model_dump(mode="json"),
        )
        return metadata

    @app.post("/documents/{document_id}/parse", response_model=ParseResult)
    def parse_document(document_id: str, dep: Container = Depends(get_container)) -> ParseResult:
        metadata = dep.repo.get_document(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")
        parser = dep.parser_registry.select(metadata)
        result = parser.parse(metadata)
        parsed_at = datetime.utcnow().isoformat()
        dep.repo.upsert_parse_result(result)
        dep.repo.update_document_parse_status(document_id, parser.name, parsed_at)
        dep.object_store.put_json(
            f"parsed/{document_id}.json",
            result.model_dump(mode="json"),
        )
        normalized = normalize_fields(result.extracted_fields)
        record = CompanyMetricRecord(
            company_code=metadata.company_code,
            company_name=metadata.company_name,
            market=metadata.market,
            fiscal_year=metadata.fiscal_year,
            currency="USD" if metadata.market == "US" else "CNY",
            normalized_fields=normalized,
        )
        dep.repo.upsert_company_metric(record)
        return result

    @app.get("/documents/{document_id}/search", response_model=SearchResult)
    def search_document(
        document_id: str,
        q: str,
        limit: int = 5,
        dep: Container = Depends(get_container),
    ) -> SearchResult:
        metadata = dep.repo.get_document(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")
        return dep.repo.search_chunks(document_id=document_id, query=q, limit=limit)

    @app.post("/documents/{document_id}/qa", response_model=QAResponse)
    def answer_question(
        document_id: str,
        payload: QARequest,
        dep: Container = Depends(get_container),
    ) -> QAResponse:
        metadata = dep.repo.get_document(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")
        query = query_from_question(payload.question)
        search_result = dep.repo.search_chunks(document_id=document_id, query=query, limit=payload.top_k)
        return build_grounded_answer(document_id=document_id, question=payload.question, search_result=search_result)

    @app.get("/filings/sample", response_model=list[SampleFiling])
    def list_sample_filings(
        market: str,
        ticker: str = "",
        dep: Container = Depends(get_container),
    ) -> list[SampleFiling]:
        if market not in {"CN_A", "HK", "US"}:
            raise HTTPException(status_code=400, detail="Unsupported market")
        return dep.filing_sources.list_sample_filings(market=market, ticker=ticker)

    @app.post("/scores/company", response_model=ScoreBreakdown)
    def score_company_endpoint(
        payload: ScoreRequest,
        dep: Container = Depends(get_container),
    ) -> ScoreBreakdown:
        record = dep.repo.get_company_metric(payload.company_code, payload.fiscal_year)
        if not record:
            raise HTTPException(status_code=404, detail="Company metric not found")
        return score_company(record)

    @app.post("/scores/compare", response_model=CompareResult)
    def compare_companies(
        payload: CompareRequest,
        dep: Container = Depends(get_container),
    ) -> CompareResult:
        records = dep.repo.list_company_metrics(payload.company_codes, payload.fiscal_year)
        if not records:
            raise HTTPException(status_code=404, detail="No company metrics found")
        ranked = sorted(
            (
                {
                    "company_code": record.company_code,
                    "company_name": record.company_name,
                    "market": record.market,
                    "score": score_company(record).model_dump(),
                }
                for record in records
            ),
            key=lambda item: item["score"]["composite_score"],
            reverse=True,
        )
        return CompareResult(fiscal_year=payload.fiscal_year, scores=ranked)

    return app


app = create_app()
