from paddleocr_quant.normalizer import normalize_field_name, normalize_fields


def test_normalize_field_name_cn_and_en():
    assert normalize_field_name("营业收入") == "REVENUE"
    assert normalize_field_name("Net sales") == "REVENUE"


def test_normalize_fields_merges_aliases():
    result = normalize_fields({"归母净利润": 1.0, "Operating cash flow": 2.0})
    assert result["NP_PARENT"] == 1.0
    assert result["OCF_NET"] == 2.0
