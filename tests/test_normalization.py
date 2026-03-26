from paddleocr_quant.models import ParsedField
from paddleocr_quant.normalization import normalize_fields


def test_normalize_fields_supports_cn_and_en_aliases() -> None:
    fields = [
        ParsedField(name="营业总收入", value=100.0, unit="CNY", source_text="营业总收入 100"),
        ParsedField(name="Net Profit", value=20.0, unit="CNY", source_text="Net Profit 20"),
    ]

    normalized = normalize_fields(fields)

    assert normalized[0].canonical_code == "revenue"
    assert normalized[1].canonical_code == "net_profit"
