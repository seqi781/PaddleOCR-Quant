from paddleocr_quant.scoring import score_company


def test_score_company_returns_positive_composite():
    score = score_company(
        "KWEICHOW_MOUTAI",
        "2025",
        {
            "REVENUE": 174140000000.0,
            "NP_PARENT": 89230000000.0,
            "OCF_NET": 93000000000.0,
            "FCF": 88000000000.0,
            "GROSS_MARGIN": 91.2,
            "ASSET_LIAB_RATIO": 21.5,
            "ROE": 34.6,
            "REVENUE_GROWTH": 15.0,
        },
    )
    assert score.composite_score > 80
    assert "经营现金流覆盖净利润，盈利质量较好" in score.notes
