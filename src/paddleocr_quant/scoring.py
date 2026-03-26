from __future__ import annotations

from .models import CompanyMetricRecord, ScoreBreakdown


def _clip(score: float) -> float:
    return max(0.0, min(100.0, round(score, 2)))


def _score_from_metrics(company_id: str, report_period: str, metrics: dict[str, float]) -> ScoreBreakdown:
    revenue = metrics.get("REVENUE", 0)
    net_profit = metrics.get("NP_PARENT", metrics.get("NET_PROFIT", 0))
    ocf = metrics.get("OCF_NET", 0)
    gross_margin = metrics.get("GROSS_MARGIN", 0)
    asset_liab_ratio = metrics.get("ASSET_LIAB_RATIO", 100)
    fcf = metrics.get("FCF", ocf * 0.8)
    roe = metrics.get("ROE", 0)
    revenue_growth = metrics.get("REVENUE_GROWTH", 0)

    quality = _clip(gross_margin * 1.2 + roe * 1.1 + (15 if ocf >= net_profit > 0 else 0))
    growth = _clip(50 + revenue_growth * 2 + min(revenue / 1e11, 20))
    cashflow = _clip(50 + min(ocf / 1e10, 20) + min(fcf / 1e10, 20) + (10 if ocf > 0 else -20))
    risk = _clip(100 - asset_liab_ratio * 0.8 - (15 if net_profit < 0 else 0))
    valuation = _clip(60 + min(roe, 20) - max(asset_liab_ratio - 40, 0) * 0.3)
    composite = _clip(quality * 0.3 + growth * 0.2 + cashflow * 0.2 + risk * 0.2 + valuation * 0.1)

    notes = []
    if ocf >= net_profit > 0:
        notes.append("经营现金流覆盖净利润，盈利质量较好")
    if asset_liab_ratio <= 50:
        notes.append("资产负债率处于可控区间")
    if revenue_growth > 0:
        notes.append("收入保持正增长")
    if fcf > 0:
        notes.append("自由现金流为正")

    return ScoreBreakdown(
        company_id=company_id,
        report_period=report_period,
        quality_score=quality,
        growth_score=growth,
        cashflow_score=cashflow,
        risk_score=risk,
        valuation_score=valuation,
        composite_score=composite,
        notes=notes,
    )


def score_company(company_or_record, report_period: str | None = None, metrics: dict[str, float] | None = None) -> ScoreBreakdown:
    if isinstance(company_or_record, CompanyMetricRecord):
        mapped = {item.canonical_code.upper(): item.value for item in company_or_record.normalized_fields}
        return _score_from_metrics(company_or_record.company_code, str(company_or_record.fiscal_year), mapped)
    if report_period is None or metrics is None:
        raise ValueError("report_period and metrics are required when scoring raw metrics")
    return _score_from_metrics(str(company_or_record), report_period, metrics)
