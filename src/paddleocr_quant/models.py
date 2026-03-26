from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


MarketCode = Literal["CN_A", "HK", "US"]


class DocumentMetadataIn(BaseModel):
    company_code: str
    company_name: str
    market: MarketCode = "CN_A"
    fiscal_year: int
    report_type: str = "annual_report"
    language: str = "zh-CN"
    source_fixture: str = Field(
        default="moutai_2023_annual_report.json",
        description="Fixture filename used by the mock parser.",
    )
    source_path: str | None = None
    tags: list[str] = Field(default_factory=list)


class DocumentMetadata(DocumentMetadataIn):
    document_id: str = Field(default_factory=lambda: f"doc-{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ParsedField(BaseModel):
    name: str
    value: float
    unit: str = "CNY"
    period: str = "FY"
    source_text: str
    page: int | None = None


class TextChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: f"chunk-{uuid4().hex[:12]}")
    document_id: str
    seq: int
    text: str
    embedding_status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParseResult(BaseModel):
    document_id: str
    parser_name: str
    extracted_fields: list[ParsedField]
    chunks: list[TextChunk]


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
