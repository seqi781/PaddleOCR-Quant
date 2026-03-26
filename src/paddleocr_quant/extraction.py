from __future__ import annotations

import re
from dataclasses import dataclass

from paddleocr_quant.models import ParsedField


@dataclass(frozen=True)
class FinancialFieldSpec:
    canonical_code: str
    label_zh: str
    label_en: str
    aliases: tuple[str, ...]
    ratio: bool = False


FIELD_SPECS: tuple[FinancialFieldSpec, ...] = (
    FinancialFieldSpec(
        canonical_code="revenue",
        label_zh="营业总收入",
        label_en="Revenue",
        aliases=("营业总收入", "营业收入", "总收入", "total revenue", "revenue"),
    ),
    FinancialFieldSpec(
        canonical_code="net_profit",
        label_zh="归母净利润",
        label_en="Net Profit",
        aliases=("归母净利润", "净利润", "本年利润", "net profit", "net income"),
    ),
    FinancialFieldSpec(
        canonical_code="operating_cashflow",
        label_zh="经营现金流净额",
        label_en="Operating Cash Flow",
        aliases=("经营活动现金流量净额", "经营现金流净额", "operating cash flow", "cash generated from operations"),
    ),
    FinancialFieldSpec(
        canonical_code="free_cash_flow",
        label_zh="自由现金流",
        label_en="Free Cash Flow",
        aliases=("自由现金流", "free cash flow"),
    ),
    FinancialFieldSpec(
        canonical_code="gross_margin",
        label_zh="毛利率",
        label_en="Gross Margin",
        aliases=("毛利率", "gross margin", "gross profit margin"),
        ratio=True,
    ),
    FinancialFieldSpec(
        canonical_code="roe",
        label_zh="净资产收益率",
        label_en="ROE",
        aliases=("净资产收益率", "加权平均净资产收益率", "roe", "return on equity"),
        ratio=True,
    ),
    FinancialFieldSpec(
        canonical_code="debt_ratio",
        label_zh="资产负债率",
        label_en="Debt Ratio",
        aliases=("资产负债率", "debt ratio", "liability ratio"),
        ratio=True,
    ),
    FinancialFieldSpec(
        canonical_code="revenue_growth",
        label_zh="营收增长率",
        label_en="Revenue Growth",
        aliases=("营收增长率", "收入增长率", "营业收入增长率", "revenue growth", "revenue growth rate"),
        ratio=True,
    ),
)

FIELD_ALIASES: dict[str, tuple[str, str, str]] = {
    alias.lower(): (spec.canonical_code, spec.label_zh, spec.label_en)
    for spec in FIELD_SPECS
    for alias in spec.aliases
}

CANONICAL_FIELD_LABELS: dict[str, tuple[str, str]] = {
    spec.canonical_code: (spec.label_zh, spec.label_en) for spec in FIELD_SPECS
}

VALUE_PATTERN = re.compile(
    r"(?P<currency>(?:RMB|CNY|USD|HKD|人民币|美元|港元|US\$|HK\$|￥|¥|\$)\s*)?"
    r"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)"
    r"\s*(?P<unit>%|亿元人民币|亿元|亿人民币|亿港元|亿美元|百万元|百亿|亿元|亿元人民币|亿|万|万元|million|billion|thousand|mn|bn|m|k)?",
    re.IGNORECASE,
)
GLOBAL_UNIT_PATTERN = re.compile(
    r"(?:单位|unit)\s*[:：]?\s*(?P<currency>人民币|RMB|CNY|USD|美元|港元|HKD)?\s*(?P<unit>亿元|亿|万元|万|million|billion|thousand|百万元)?",
    re.IGNORECASE,
)

MULTIPLIERS: dict[str, float] = {
    "亿": 1e8,
    "亿元": 1e8,
    "亿元人民币": 1e8,
    "亿人民币": 1e8,
    "亿美元": 1e8,
    "亿港元": 1e8,
    "万": 1e4,
    "万元": 1e4,
    "百万元": 1e6,
    "million": 1e6,
    "mn": 1e6,
    "m": 1e6,
    "billion": 1e9,
    "bn": 1e9,
    "百亿": 1e10,
    "thousand": 1e3,
    "k": 1e3,
}

CURRENCY_HINTS: dict[str, str] = {
    "人民币": "CNY",
    "rmb": "CNY",
    "cny": "CNY",
    "￥": "CNY",
    "¥": "CNY",
    "美元": "USD",
    "usd": "USD",
    "us$": "USD",
    "$": "USD",
    "港元": "HKD",
    "hkd": "HKD",
    "hk$": "HKD",
}


def extract_financial_fields(
    text: str,
    *,
    page_number: int | None = None,
    default_currency: str = "CNY",
) -> list[ParsedField]:
    if not text.strip():
        return []

    lines = _candidate_lines(text)
    global_hint = detect_global_unit_hint(text)
    extracted: list[ParsedField] = []
    seen: set[tuple[str, int | None, float, str]] = set()

    for line in lines:
        consumed_spans: list[tuple[int, int]] = []
        for spec, alias, alias_span in _iter_alias_matches(line):
            if any(_spans_overlap(alias_span, consumed) for consumed in consumed_spans):
                continue
            value_match = _find_value_after_alias(line, alias) or VALUE_PATTERN.search(line)
            if not value_match:
                continue
            parsed = parse_value_with_unit(
                raw_value=value_match.group("value"),
                raw_currency=(value_match.group("currency") or ""),
                raw_unit=(value_match.group("unit") or ""),
                line=line,
                default_currency=default_currency,
                global_hint=global_hint,
                ratio=spec.ratio,
            )
            if parsed is None:
                continue
            value, unit, metadata = parsed
            dedupe_key = (spec.canonical_code, page_number, round(value, 6), unit)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            consumed_spans.append(alias_span)
            extracted.append(
                ParsedField(
                    name=alias,
                    canonical_code=spec.canonical_code,
                    value=value,
                    unit=unit,
                    source_text=line,
                    page=page_number,
                    metadata={
                        "matched_alias": alias,
                        "raw_value": value_match.group("value"),
                        **metadata,
                    },
                )
            )
    return extracted


def parse_value_with_unit(
    *,
    raw_value: str,
    raw_currency: str = "",
    raw_unit: str = "",
    line: str = "",
    default_currency: str = "CNY",
    global_hint: dict[str, str | float] | None = None,
    ratio: bool = False,
) -> tuple[float, str, dict[str, str | float]] | None:
    try:
        numeric = _parse_numeric_token(raw_value)
    except ValueError:
        return None

    line_hint = detect_global_unit_hint(line)
    multiplier = 1.0
    detected_unit = (raw_unit or "").strip()
    if detected_unit:
        multiplier = MULTIPLIERS.get(detected_unit.lower(), MULTIPLIERS.get(detected_unit, 1.0))
    elif line_hint.get("multiplier"):
        multiplier = float(line_hint["multiplier"])
        detected_unit = str(line_hint.get("raw_unit") or "")
    elif global_hint and global_hint.get("multiplier"):
        multiplier = float(global_hint["multiplier"])
        detected_unit = str(global_hint.get("raw_unit") or "")

    currency = detect_currency(raw_currency or line, default_currency=default_currency)
    if not raw_currency and line_hint.get("currency"):
        currency = str(line_hint["currency"])
    elif not raw_currency and global_hint and global_hint.get("currency"):
        currency = str(global_hint["currency"])

    if ratio or "%" in raw_unit or "%" in line:
        return (
            numeric,
            "%",
            {
                "detected_currency": currency,
                "raw_unit": detected_unit or "%",
                "multiplier": 1.0,
            },
        )

    return (
        numeric * multiplier,
        currency,
        {
            "detected_currency": currency,
            "raw_unit": detected_unit,
            "multiplier": multiplier,
        },
    )


def detect_global_unit_hint(text: str) -> dict[str, str | float]:
    match = GLOBAL_UNIT_PATTERN.search(text)
    if not match:
        return {}
    raw_unit = (match.group("unit") or "").strip()
    raw_currency = (match.group("currency") or "").strip()
    return {
        "raw_unit": raw_unit,
        "multiplier": MULTIPLIERS.get(raw_unit.lower(), MULTIPLIERS.get(raw_unit, 1.0)),
        "currency": detect_currency(raw_currency, default_currency="CNY"),
    }


def detect_currency(text: str, default_currency: str = "CNY") -> str:
    lowered = text.lower()
    for hint, code in CURRENCY_HINTS.items():
        if hint.lower() in lowered:
            return code
    return default_currency


def _candidate_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" \t|")
        if line:
            lines.append(line)
    return lines


def _match_alias(line: str, aliases: tuple[str, ...]) -> str | None:
    for alias in sorted(aliases, key=len, reverse=True):
        if _alias_regex(alias).search(line):
            return alias
    return None


def _find_value_after_alias(line: str, alias: str) -> re.Match[str] | None:
    match = _alias_regex(alias).search(line)
    if not match:
        return None
    return VALUE_PATTERN.search(line[match.end() :])


def _iter_alias_matches(line: str) -> list[tuple[FinancialFieldSpec, str, tuple[int, int]]]:
    matches: list[tuple[FinancialFieldSpec, str, tuple[int, int]]] = []
    for spec in FIELD_SPECS:
        for alias in sorted(spec.aliases, key=len, reverse=True):
            match = _alias_regex(alias).search(line)
            if match:
                matches.append((spec, alias, match.span()))
    return sorted(matches, key=lambda item: (item[2][1] - item[2][0]), reverse=True)


def _alias_regex(alias: str) -> re.Pattern[str]:
    if re.search(r"[A-Za-z]", alias):
        return re.compile(rf"(?i)\b{re.escape(alias)}\b")
    return re.compile(re.escape(alias))


def _spans_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _parse_numeric_token(token: str) -> float:
    cleaned = token.replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    return float(cleaned)
