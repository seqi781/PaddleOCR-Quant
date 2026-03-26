from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


MarketCode = Literal["CN_A", "HK", "US"]
SourceType = Literal["fixture", "local"]
ParseStrategy = Literal["text", "ocr", "mock"]
OCRPageStatus = Literal["not_run", "success", "warning", "unavailable"]


class DocumentMetadataIn(BaseModel):
    company_code: str
    company_name: str
    market: MarketCode = "CN_A"
    fiscal_year: int
    report_type: str = "annual_report"
    language: str = "zh-CN"
    source_fixture: str | None = Field(
        default="moutai_2023_annual_report.json",
        description="Fixture filename used by the mock parser.",
    )
    source_path: str | None = None
    parser_hint: str | None = None
    tags: list[str] = Field(default_factory=list)


class DocumentMetadata(DocumentMetadataIn):
    document_id: str = Field(default_factory=lambda: f"doc-{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_type: SourceType = "fixture"
    file_hash: str | None = None
    stored_path: str | None = None
    detected_extension: str | None = None
    mime_type: str | None = None
    parser_name: str | None = None
    parsed_at: datetime | None = None


class ParsedField(BaseModel):
    name: str
    canonical_code: str | None = None
    value: float
    unit: str = "CNY"
    period: str = "FY"
    source_text: str
    page: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: f"chunk-{uuid4().hex[:12]}")
    document_id: str
    seq: int
    text: str
    score: float = 0.0
    embedding_status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRPageResult(BaseModel):
    page_number: int
    status: OCRPageStatus = "not_run"
    image_path: str | None = None
    extracted_text: str = ""
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentInspection(BaseModel):
    document_id: str
    parser_name: str
    recommended_strategy: ParseStrategy
    detected_extension: str | None = None
    source_type: SourceType
    text_extractable: bool | None = None
    page_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParseResult(BaseModel):
    document_id: str
    parser_name: str
    strategy: ParseStrategy = "text"
    extracted_text: str = ""
    extracted_fields: list[ParsedField]
    chunks: list[TextChunk]
    page_results: list[OCRPageResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedField(BaseModel):
    canonical_code: str
    label_zh: str
    label_en: str
    value: float
    unit: str
    source_name: str


class CompanyMetricRecord(BaseModel):
    company_code: str
    company_name: str
    market: MarketCode
    fiscal_year: int
    currency: str = "CNY"
    normalized_fields: list[NormalizedField]


class ScoreBreakdown(BaseModel):
    company_id: str
    report_period: str
    quality_score: float
    growth_score: float
    cashflow_score: float
    risk_score: float
    valuation_score: float
    composite_score: float
    notes: list[str] = Field(default_factory=list)


class ScoreRequest(BaseModel):
    company_code: str
    fiscal_year: int


class CompareRequest(BaseModel):
    company_codes: list[str]
    fiscal_year: int


class CompareResult(BaseModel):
    fiscal_year: int
    scores: list[dict[str, Any]]


class SearchResult(BaseModel):
    document_id: str
    query: str
    total_hits: int
    chunks: list[TextChunk]


class QARequest(BaseModel):
    question: str
    top_k: int = 3


class Citation(BaseModel):
    chunk_id: str
    seq: int
    snippet: str


class QAResponse(BaseModel):
    document_id: str
    question: str
    answer: str
    citations: list[Citation]


class SampleFiling(BaseModel):
    market: MarketCode
    ticker: str
    title: str
    report_type: str
    filing_date: str
    source_url: str
    local_fixture: str


class FieldExtractionResult(BaseModel):
    document_id: str | None = None
    source: str
    extracted_fields: list[ParsedField]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
