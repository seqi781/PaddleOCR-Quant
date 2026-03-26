from __future__ import annotations

from paddleocr_quant.models import NormalizedField, ParsedField


FIELD_ALIASES: dict[str, tuple[str, str, str]] = {
    "营业总收入": ("revenue", "营业总收入", "Revenue"),
    "营业收入": ("revenue", "营业总收入", "Revenue"),
    "total revenue": ("revenue", "营业总收入", "Revenue"),
    "revenue": ("revenue", "营业总收入", "Revenue"),
    "归母净利润": ("net_profit", "归母净利润", "Net Profit"),
    "净利润": ("net_profit", "归母净利润", "Net Profit"),
    "net profit": ("net_profit", "归母净利润", "Net Profit"),
    "net income": ("net_profit", "归母净利润", "Net Profit"),
    "经营活动现金流量净额": ("operating_cashflow", "经营现金流净额", "Operating Cash Flow"),
    "operating cash flow": ("operating_cashflow", "经营现金流净额", "Operating Cash Flow"),
    "净资产收益率": ("roe", "净资产收益率", "ROE"),
    "roe": ("roe", "净资产收益率", "ROE"),
    "gross margin": ("gross_margin", "毛利率", "Gross Margin"),
    "毛利率": ("gross_margin", "毛利率", "Gross Margin"),
    "资产负债率": ("debt_ratio", "资产负债率", "Debt Ratio"),
    "debt ratio": ("debt_ratio", "资产负债率", "Debt Ratio"),
    "revenue growth": ("revenue_growth", "营收增长率", "Revenue Growth"),
    "营收增长率": ("revenue_growth", "营收增长率", "Revenue Growth"),
    "net profit growth": ("profit_growth", "净利润增长率", "Net Profit Growth"),
    "净利润增长率": ("profit_growth", "净利润增长率", "Net Profit Growth"),
}


def normalize_field_name(name: str) -> tuple[str, str, str]:
    key = name.strip().lower()
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    return (key.replace(" ", "_"), name, name)


def normalize_fields(fields: list[ParsedField]) -> list[NormalizedField]:
    normalized: list[NormalizedField] = []
    for field in fields:
        canonical_code, label_zh, label_en = normalize_field_name(field.name)
        normalized.append(
            NormalizedField(
                canonical_code=canonical_code,
                label_zh=label_zh,
                label_en=label_en,
                value=field.value,
                unit=field.unit,
                source_name=field.name,
            )
        )
    return normalized
