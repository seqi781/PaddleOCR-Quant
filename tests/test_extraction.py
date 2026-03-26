from paddleocr_quant.extraction import detect_global_unit_hint, extract_financial_fields, parse_value_with_unit


def test_parse_value_with_unit_handles_multipliers_and_ratio_units() -> None:
    chinese = parse_value_with_unit(
        raw_value="12.5",
        raw_unit="亿",
        line="营业收入 12.5 亿",
        default_currency="CNY",
    )
    english = parse_value_with_unit(
        raw_value="320",
        raw_currency="USD",
        raw_unit="million",
        line="Net profit USD 320 million",
        default_currency="CNY",
    )
    ratio = parse_value_with_unit(
        raw_value="44.5",
        raw_unit="%",
        line="Gross margin 44.5%",
        default_currency="USD",
        ratio=True,
    )

    assert chinese == (1_250_000_000.0, "CNY", {"detected_currency": "CNY", "raw_unit": "亿", "multiplier": 1e8})
    assert english == (
        320_000_000.0,
        "USD",
        {"detected_currency": "USD", "raw_unit": "million", "multiplier": 1e6},
    )
    assert ratio == (44.5, "%", {"detected_currency": "USD", "raw_unit": "%", "multiplier": 1.0})


def test_extract_financial_fields_handles_mixed_language_units_and_evidence() -> None:
    text = """
    单位：亿元人民币
    营业收入：12.5
    净利润：3.2
    Operating cash flow: USD 850 million
    Gross margin: 44.5%
    ROE: 18.2%
    Debt ratio 37%
    Revenue growth 12.3%
    Free cash flow RMB 1.6 billion
    """.strip()

    hint = detect_global_unit_hint(text)
    fields = extract_financial_fields(text, default_currency="CNY")
    by_code = {field.canonical_code: field for field in fields}

    assert hint["multiplier"] == 1e8
    assert by_code["revenue"].value == 1_250_000_000.0
    assert by_code["net_profit"].value == 320_000_000.0
    assert by_code["operating_cashflow"].value == 850_000_000.0
    assert by_code["operating_cashflow"].unit == "USD"
    assert by_code["gross_margin"].unit == "%"
    assert by_code["gross_margin"].value == 44.5
    assert by_code["free_cash_flow"].value == 1_600_000_000.0
    assert "matched_alias" in by_code["free_cash_flow"].metadata
    assert "Free cash flow" in by_code["free_cash_flow"].source_text
