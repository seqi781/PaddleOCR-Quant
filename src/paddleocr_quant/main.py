from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from paddleocr_quant.bootstrap import Container, build_container
from paddleocr_quant.models import (
    CompareRequest,
    CompareResult,
    CompanyMetricRecord,
    DocumentMetadata,
    DocumentMetadataIn,
    ParseResult,
    ScoreBreakdown,
    ScoreRequest,
)
from paddleocr_quant.normalization import normalize_fields
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
        metadata = DocumentMetadata(**payload.model_dump())
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
        result = dep.parser.parse(metadata)
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
